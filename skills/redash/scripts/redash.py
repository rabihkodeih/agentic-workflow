#!/usr/bin/env python3
"""Redash REST API client, stdlib only, no pip install.

Auth: user API key, resolved (in order) from $REDASH_API_KEY, the macOS keychain
item `redash-api-key`, or ~/.config/redash/api.key.
Base URL: $REDASH_URL, or ~/.config/redash/url.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KEYCHAIN_SERVICE = "redash-api-key"
KEYFILE = os.path.expanduser("~/.config/redash/api.key")
URLFILE = os.path.expanduser("~/.config/redash/url")


def _base_url():
    url = os.environ.get("REDASH_URL", "").strip()
    if not url and os.path.exists(URLFILE):
        with open(URLFILE) as fh:
            url = fh.read().strip()
    if not url:
        print("NO URL. export REDASH_URL=https://redash.example.com or write it to %s" % URLFILE, file=sys.stderr)
        sys.exit(1)
    return url.rstrip("/")


BASE = _base_url()
USER_AGENT = os.environ.get(
    "REDASH_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
)
KEY = None  # filled by resolve_key()

EXIT_AUTH = 2
EXIT_REFUSED = 3
EXIT_TIMEOUT = 4
EXIT_HTTP = 5
EXIT_NETWORK = 6


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------- credentials


def resolve_key():
    key = os.environ.get("REDASH_API_KEY")
    if key:
        return key.strip()
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    if os.path.exists(KEYFILE):
        with open(KEYFILE) as fh:
            val = fh.read().strip()
            if val:
                return val
    die(
        "NO API KEY. Store it once (the key never enters the transcript):\n"
        f"  security add-generic-password -a \"$USER\" -s {KEYCHAIN_SERVICE} -w\n"
        "(paste the key at the prompt), or export REDASH_API_KEY=...\n"
        f"Get the key at {BASE}/users/me (Account -> API Key).",
        EXIT_AUTH,
    )


# ------------------------------------------------------------------- http


def api(path, method="GET", body=None, timeout=60):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Key %s" % KEY)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    # Cloudflare fronts this host and 403s the default Python-urllib signature
    # (error 1010, browser_signature_banned) before the API key is ever read.
    req.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:600]
        if exc.code in (401, 403):
            die(
                "AUTH: Redash returned %d , the API key is rejected or lacks access "
                "to that object.\n%s" % (exc.code, detail),
                EXIT_AUTH,
            )
        if exc.code == 404:
            # Redash answers unauthenticated API calls with 404, not 401.
            hint = " (Redash returns 404 for an unauthenticated call , check the key.)" \
                if path.startswith("/api/session") else ""
            die("NOT FOUND: %s%s\n%s" % (path, hint, detail), EXIT_HTTP)
        die("HTTP %d on %s %s\n%s" % (exc.code, method, path, detail), EXIT_HTTP)
    except urllib.error.URLError as exc:
        die("NETWORK: cannot reach %s (%s)" % (BASE, exc.reason), EXIT_NETWORK)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        die("Non-JSON reply from %s (are you behind an SSO wall?):\n%s"
            % (path, raw[:300].decode("utf-8", "replace")), EXIT_HTTP)


# -------------------------------------------------------------- read-only guard

_ALLOWED = re.compile(r"^\s*\(*\s*(select|with|show|describe|desc|explain|pragma)\b", re.I)
_WRITES_FILE = re.compile(r"\binto\s+(outfile|dumpfile)\b", re.I)


def _blank_literals(sql):
    """Replace string literals and comments with spaces so the guard can't be
    fooled by a ';' or a keyword sitting inside quotes."""
    out = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in ("'", '"', "`"):
            quote = ch
            out.append(" ")
            i += 1
            while i < n:
                if sql[i] == "\\" and quote != "`":
                    out.append("  ")
                    i += 2
                    continue
                if sql[i] == quote:
                    if i + 1 < n and sql[i + 1] == quote:
                        out.append("  ")
                        i += 2
                        continue
                    out.append(" ")
                    i += 1
                    break
                out.append(" ")
                i += 1
            continue
        if sql.startswith("--", i) or sql.startswith("#", i):
            while i < n and sql[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if sql.startswith("/*", i):
            while i < n and not sql.startswith("*/", i):
                out.append(" ")
                i += 1
            out.append("  ")
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def assert_read_only(sql):
    stripped = _blank_literals(sql)
    if not _ALLOWED.match(stripped):
        die(
            "REFUSED: only SELECT / WITH / SHOW / DESCRIBE / EXPLAIN are allowed.\n"
            "Pass --unsafe if you genuinely intend a writing statement.",
            EXIT_REFUSED,
        )
    if _WRITES_FILE.search(stripped):
        die("REFUSED: statement writes to a file (INTO OUTFILE/DUMPFILE).", EXIT_REFUSED)
    body, _, tail = stripped.partition(";")
    if tail.strip():
        die("REFUSED: one statement per call (stacked statements after ';').", EXIT_REFUSED)
    return body


# ---------------------------------------------------------------- job polling


def wait_for_result(reply, timeout):
    """Accepts the reply of a query-execution POST, returns a query_result dict."""
    if "query_result" in reply:
        return reply["query_result"]
    job = reply.get("job")
    if not job:
        die("Unexpected reply from Redash: %s" % json.dumps(reply)[:400], EXIT_HTTP)
    job_id = job["id"]
    deadline = time.time() + timeout
    delay = 0.4
    while True:
        cur = api("/api/jobs/%s" % job_id).get("job", {})
        status = int(cur.get("status", 0))
        if status == 3:
            rid = cur.get("query_result_id")
            return api("/api/query_results/%s" % rid)["query_result"]
        if status == 4:
            die("QUERY FAILED: %s" % cur.get("error", "(no message)"), EXIT_REFUSED)
        if status == 5:
            die("QUERY CANCELLED by Redash.", EXIT_REFUSED)
        if time.time() > deadline:
            api("/api/jobs/%s" % job_id, method="DELETE")
            die(
                "TIMEOUT: no result after %ds; the job was cancelled. Narrow the "
                "query or raise --timeout." % timeout,
                EXIT_TIMEOUT,
            )
        time.sleep(delay)
        delay = min(delay * 1.4, 3.0)


# ------------------------------------------------------------------ rendering


def _cell(value, width):
    if value is None:
        text = "NULL"
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, default=str)
    else:
        text = str(value)
    text = text.replace("\n", " ").replace("\t", " ")
    if len(text) > width:
        text = text[: width - 1] + "…"
    return text


def render(result, fmt, limit, width):
    data = result.get("data") or {}
    cols = [c["name"] for c in data.get("columns", [])]
    rows = data.get("rows", [])
    truncated = len(rows) > limit
    rows = rows[:limit]

    if fmt == "json":
        print(json.dumps(rows, indent=2, default=str))
    elif fmt == "csv":
        import csv

        writer = csv.DictWriter(sys.stdout, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c) for c in cols})
    else:
        if not cols:
            print("(no columns)")
        else:
            cells = [[_cell(r.get(c), width) for c in cols] for r in rows]
            widths = [
                max(len(c), *(len(row[i]) for row in cells)) if cells else len(c)
                for i, c in enumerate(cols)
            ]
            line = "  ".join(c.ljust(widths[i]) for i, c in enumerate(cols))
            print(line)
            print("  ".join("-" * w for w in widths))
            for row in cells:
                print("  ".join(row[i].ljust(widths[i]) for i in range(len(cols))))

    meta = "%d row(s)" % len(rows)
    if truncated:
        meta += " (truncated at --limit; more available)"
    if result.get("runtime") is not None:
        meta += " · %.2fs runtime" % result["runtime"]
    if result.get("retrieved_at"):
        meta += " · retrieved_at %s" % result["retrieved_at"]
    print("\n" + meta, file=sys.stderr)


# ------------------------------------------------------------------ commands


def cmd_whoami(args):
    me = api("/api/session").get("user", {})
    print(json.dumps({k: me.get(k) for k in ("id", "name", "email", "groups")}, indent=2))


def cmd_datasources(args):
    for ds in api("/api/data_sources"):
        print("%-5s %-14s %s" % (ds["id"], ds.get("type", "?"), ds.get("name", "")))


def cmd_schema(args):
    payload = api("/api/data_sources/%s/schema" % args.data_source, timeout=120)
    tables = payload.get("schema", payload)
    if args.format == "json":
        print(json.dumps(tables, indent=2))
        return
    for table in tables:
        cols = table.get("columns", [])
        names = [c["name"] if isinstance(c, dict) else c for c in cols]
        if args.grep and args.grep.lower() not in table["name"].lower():
            continue
        print("%s(%s)" % (table["name"], ", ".join(names)))


def cmd_queries(args):
    params = {"page": args.page, "page_size": args.page_size}
    if args.search:
        params["q"] = args.search
    payload = api("/api/queries?" + urllib.parse.urlencode(params))
    results = payload.get("results", [])
    for q in results:
        ds = q.get("data_source_id")
        print("%-7s ds=%-3s %-19s %s"
              % (q["id"], ds, (q.get("updated_at") or "")[:19], q.get("name", "")))
    print("\n%d of %d match(es), page %s"
          % (len(results), payload.get("count", len(results)), payload.get("page", 1)),
          file=sys.stderr)


def cmd_get(args):
    q = api("/api/queries/%s" % args.query_id)
    if args.format == "json":
        print(json.dumps(q, indent=2))
        return
    print("# %s (id=%s, data_source_id=%s)" % (q.get("name"), q["id"], q.get("data_source_id")))
    if q.get("description"):
        print("# %s" % q["description"])
    params = (q.get("options") or {}).get("parameters") or []
    for p in params:
        print("# param: %s (%s) default=%r" % (p.get("name"), p.get("type"), p.get("value")))
    print()
    print(q.get("query", ""))


def _parse_params(pairs):
    out = {}
    for item in pairs or []:
        if "=" not in item:
            die("--param expects key=value, got %r" % item)
        key, _, value = item.partition("=")
        try:
            out[key] = json.loads(value)
        except ValueError:
            out[key] = value
    return out


def cmd_run(args):
    body = {"parameters": _parse_params(args.param), "max_age": args.max_age}
    reply = api("/api/queries/%s/results" % args.query_id, method="POST", body=body)
    result = wait_for_result(reply, args.timeout)
    render(result, args.format, args.limit, args.width)


def cmd_query(args):
    sql = args.sql
    if sql == "-":
        sql = sys.stdin.read()
    if not args.unsafe:
        assert_read_only(sql)
    body = {
        "query": sql,
        "data_source_id": int(args.data_source),
        "max_age": args.max_age,
        "parameters": _parse_params(args.param),
    }
    reply = api("/api/query_results", method="POST", body=body)
    result = wait_for_result(reply, args.timeout)
    render(result, args.format, args.limit, args.width)


def cmd_dashboards(args):
    params = {"page": args.page, "page_size": args.page_size}
    if args.search:
        params["q"] = args.search
    payload = api("/api/dashboards?" + urllib.parse.urlencode(params))
    for d in payload.get("results", []):
        print("%-7s %-28s %s" % (d.get("id"), d.get("slug", ""), d.get("name", "")))


def cmd_dashboard(args):
    d = api("/api/dashboards/%s" % args.dashboard)
    if args.format == "json":
        print(json.dumps(d, indent=2))
        return
    print("# %s (id=%s slug=%s)" % (d.get("name"), d.get("id"), d.get("slug")))
    for widget in d.get("widgets", []):
        viz = widget.get("visualization") or {}
        q = viz.get("query") or {}
        if q:
            print("query %-7s %-22s %s" % (q.get("id"), viz.get("name", "")[:22], q.get("name")))


def cmd_raw(args):
    body = json.loads(args.body) if args.body else None
    print(json.dumps(api(args.path, method=args.method, body=body), indent=2, default=str))


# --------------------------------------------------------------------- main


def build_parser():
    p = argparse.ArgumentParser(prog="redash.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_output(sp, default_fmt="table"):
        sp.add_argument("--format", choices=["table", "json", "csv"], default=default_fmt)
        sp.add_argument("--limit", type=int, default=200, help="max rows printed (default 200)")
        sp.add_argument("--width", type=int, default=48, help="max column width (default 48)")
        sp.add_argument("--timeout", type=int, default=180, help="seconds to wait (default 180)")
        sp.add_argument("--max-age", type=int, default=0,
                        help="accept a cached result younger than N seconds (0 = always fresh)")
        sp.add_argument("--param", action="append", help="key=value, repeatable")

    sp = sub.add_parser("whoami", help="verify the API key")
    sp.set_defaults(func=cmd_whoami)

    sp = sub.add_parser("datasources", help="list data sources with their ids")
    sp.set_defaults(func=cmd_datasources)

    sp = sub.add_parser("schema", help="tables and columns of a data source")
    sp.add_argument("data_source")
    sp.add_argument("--grep", help="only tables whose name contains this")
    sp.add_argument("--format", choices=["table", "json"], default="table")
    sp.set_defaults(func=cmd_schema)

    sp = sub.add_parser("queries", help="list/search saved queries")
    sp.add_argument("search", nargs="?")
    sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--page-size", type=int, default=50)
    sp.set_defaults(func=cmd_queries)

    sp = sub.add_parser("get", help="show a saved query's SQL and parameters")
    sp.add_argument("query_id")
    sp.add_argument("--format", choices=["table", "json"], default="table")
    sp.set_defaults(func=cmd_get)

    sp = sub.add_parser("run", help="execute a saved query by id")
    sp.add_argument("query_id")
    add_output(sp)
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("query", help="run ad-hoc SQL against a data source")
    sp.add_argument("sql", help="the SQL, or '-' to read stdin")
    sp.add_argument("--data-source", "-d", required=True, help="data source id (see `datasources`)")
    sp.add_argument("--unsafe", action="store_true", help="skip the read-only guard")
    add_output(sp)
    sp.set_defaults(func=cmd_query)

    sp = sub.add_parser("dashboards", help="list/search dashboards")
    sp.add_argument("search", nargs="?")
    sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--page-size", type=int, default=50)
    sp.set_defaults(func=cmd_dashboards)

    sp = sub.add_parser("dashboard", help="show a dashboard's widgets and their query ids")
    sp.add_argument("dashboard", help="id or slug")
    sp.add_argument("--format", choices=["table", "json"], default="table")
    sp.set_defaults(func=cmd_dashboard)

    sp = sub.add_parser("raw", help="call any API path directly")
    sp.add_argument("path", help="e.g. /api/users")
    sp.add_argument("--method", default="GET")
    sp.add_argument("--body", help="JSON string")
    sp.set_defaults(func=cmd_raw)

    return p


def main():
    global KEY
    args = build_parser().parse_args()
    KEY = resolve_key()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
