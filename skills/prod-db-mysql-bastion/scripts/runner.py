"""Read-only SQL runner, executes INSIDE the VPC (on the bastion EC2).

Piped to the EC2's python over SSH-via-SSM by query.sh; never runs on the laptop
(the prod RDS Proxy has no public endpoint). Reads DB credentials from Secrets
Manager via the instance role, so no password ever reaches the caller's session.

Read-only is enforced in three layers, weakest to strongest:
  1. statement allow-list  , SELECT/WITH/SHOW/DESCRIBE/EXPLAIN only, single statement
  2. no-file-write check   , rejects INTO OUTFILE / INTO DUMPFILE (a SELECT that writes)
  3. START TRANSACTION READ ONLY , the server itself rejects any write (error 1792)

Layer 3 is the one that actually holds: the DB user may have full privileges (many
shops have no read-only DB role), so a regex is not a security boundary but the storage
engine is. Layers 1-2 exist to fail fast with a clear message.
"""

from __future__ import annotations

import base64
import json
import re
import sys
import time

# boto3 and pymysql are imported where used so test_guard.py runs with a plain python3.

ALLOWED_STARTERS = {"select", "with", "show", "describe", "desc", "explain"}
FILE_WRITE = re.compile(r"\binto\s+(outfile|dumpfile)\b", re.IGNORECASE)

# Set by main(); read by the top-level error handler to name the limit that fired.
TIMEOUT_S = 0


def scrub(sql: str) -> str:
    """Blank out string literals and comments so the guards can't be fooled by them.

    `SELECT '; DROP TABLE x'` must not look like a stacked statement, and
    `-- INTO OUTFILE` must not look like a file write.
    """
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c in "'\"`":
            quote, i = c, i + 1
            while i < n:
                if sql[i] == "\\" and quote != "`":
                    i += 2
                    continue
                if sql[i] == quote:
                    if i + 1 < n and sql[i + 1] == quote:  # '' escape
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(" ")
            continue
        if sql.startswith("--", i) or c == "#":
            while i < n and sql[i] != "\n":
                i += 1
            out.append(" ")
            continue
        if sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
            out.append(" ")
            continue
        out.append(c)
        i += 1
    return "".join(out)


def guard(sql: str) -> None:
    body = scrub(sql).strip()
    if not body:
        raise ValueError("empty statement")
    if body.endswith(";"):
        body = body[:-1].rstrip()
    if ";" in body:
        raise ValueError("multiple statements are not allowed , send one query at a time")
    starter = re.match(r"[A-Za-z]+", body)
    word = starter.group(0).lower() if starter else ""
    if word not in ALLOWED_STARTERS:
        raise ValueError(
            f"'{word.upper() or sql.strip()[:20]}' is not a read-only statement; "
            f"allowed: {', '.join(sorted(ALLOWED_STARTERS)).upper()}"
        )
    if FILE_WRITE.search(body):
        raise ValueError("INTO OUTFILE / INTO DUMPFILE writes to disk , refused")


def credentials(secret_id: str, region: str) -> tuple[str, str]:
    import boto3

    raw = boto3.client("secretsmanager", region_name=region).get_secret_value(
        SecretId=secret_id
    )["SecretString"]
    secret = json.loads(raw)
    user = secret.get("username") or secret.get("user")
    password = secret.get("password") or secret.get("pass")
    if not user or not password:
        raise RuntimeError(f"secret has no usable user/password keys: {sorted(secret)}")
    return user, password


def jsonable(value):
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", "replace")
    return str(value)


def render_table(columns: list[str], rows: list[dict]) -> str:
    if not columns:
        return "(no columns)"
    cells = [[("NULL" if r[c] is None else str(r[c])) for c in columns] for r in rows]
    widths = [
        max(len(col), *(len(row[i]) for row in cells)) if cells else len(col)
        for i, col in enumerate(columns)
    ]
    sep = "-+-".join("-" * w for w in widths)
    lines = [" | ".join(c.ljust(w) for c, w in zip(columns, widths)), sep]
    lines += [" | ".join(c.ljust(w) for c, w in zip(row, widths)) for row in cells]
    return "\n".join(lines)


def main() -> int:
    global TIMEOUT_S
    req = json.loads(base64.b64decode(sys.argv[1]))
    sql: str = req["sql"]
    limit: int = req["limit"]
    timeout_s: int = req["timeout"]
    fmt: str = req["format"]
    TIMEOUT_S = timeout_s

    guard(sql)
    import pymysql

    user, password = credentials(req["secret_id"], req["region"])

    conn = pymysql.connect(
        host=req["host"],
        port=req["port"],
        user=user,
        password=password,
        database=req["database"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        charset="utf8mb4",
        # `{"ca": None}` , not `{}` , is the shape that actually triggers pymysql's
        # TLS path; the proxy rejects a plaintext connection (3159).
        ssl={"ca": None},
        read_timeout=timeout_s + 5,
        connect_timeout=15,
    )
    try:
        with conn.cursor() as cur:
            # Caps server-side SELECT runtime , the guard that matters day to day on a
            # live prod cluster, where an unbounded join pins a proxy connection.
            cur.execute("SET SESSION max_execution_time = %s", (timeout_s * 1000,))
            cur.execute("START TRANSACTION READ ONLY")
            started = time.monotonic()
            cur.execute(sql)
            rows = cur.fetchmany(limit + 1)
            duration_ms = int((time.monotonic() - started) * 1000)
            columns = [d[0] for d in cur.description] if cur.description else []
        conn.rollback()
    finally:
        conn.close()

    truncated = len(rows) > limit
    rows = rows[:limit]

    if fmt == "table":
        print(render_table(columns, rows))
        print(f"\n({len(rows)} rows, {duration_ms} ms{', TRUNCATED' if truncated else ''})")
    else:
        print(
            json.dumps(
                {
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                    "truncated": truncated,
                    "duration_ms": duration_ms,
                },
                default=jsonable,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    import pymysql

    try:
        sys.exit(main())
    except ValueError as exc:  # guard rejection , the caller's SQL is not read-only
        print(f"REFUSED: {exc}", file=sys.stderr)
        sys.exit(3)
    except pymysql.err.OperationalError as exc:
        code = exc.args[0] if exc.args else None
        if code == 1792:  # ER_CANT_EXECUTE_IN_READ_ONLY_TRANSACTION
            print("REFUSED: write attempted inside a read-only transaction", file=sys.stderr)
            sys.exit(3)
        if code == 3024:  # ER_QUERY_TIMEOUT
            print(f"TIMEOUT: query exceeded {TIMEOUT_S}s and was killed", file=sys.stderr)
            sys.exit(4)
        raise
