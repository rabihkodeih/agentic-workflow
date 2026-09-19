#!/usr/bin/env python3
"""Read-only guard for production Postgres SQL: allow one SELECT/WITH/VALUES/SHOW/EXPLAIN
statement (or a psql describe meta-command), refuse anything else.

Usage: guard.py '<sql>'  -> exit 0 (ok) / 3 (refused, reason on stderr).
The server enforces read-only too (default_transaction_read_only); this exists
to fail fast with a clear message before a tunnel is opened.
"""
import re
import sys

ALLOWED_FIRST = ("SELECT", "WITH", "VALUES", "SHOW", "EXPLAIN", "TABLE")
META_OK = re.compile(r"^\\(d[a-zA-Z+]*|l\+?|dn\+?|df\+?|di\+?|dv\+?|z)(\s|$)")


def _blank(sql: str) -> str:
    """Blank string literals, dollar-quoted strings, identifiers and comments."""
    out, i, n = [], 0, len(sql)
    while i < n:
        c = sql[i]
        if c == "'" or c == '"':
            j = i + 1
            while j < n:
                if sql[j] == c:
                    if j + 1 < n and sql[j + 1] == c:
                        j += 2
                        continue
                    break
                j += 1
            out.append(" " * (j - i + 1))
            i = j + 1
        elif c == "$":
            m = re.match(r"\$[A-Za-z_]*\$", sql[i:])
            if m:
                tag = m.group(0)
                j = sql.find(tag, i + len(tag))
                j = n if j < 0 else j + len(tag)
                out.append(" " * (j - i))
                i = j
            else:
                out.append(c)
                i += 1
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(" " * (j - i))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def check(sql: str) -> str | None:
    """Return a refusal reason, or None when the statement is read-only."""
    stripped = sql.strip()
    if not stripped:
        return "empty statement"
    if stripped.startswith("\\"):
        return None if META_OK.match(stripped) else "only describe meta-commands (\\d, \\dt, \\l ...) are allowed"
    blanked = _blank(sql).strip().rstrip(";").strip()
    if ";" in blanked:
        return "one statement per call"
    first = re.split(r"[\s(]", blanked, maxsplit=1)[0].upper()
    if first not in ALLOWED_FIRST:
        return "not a read-only statement (starts with %s)" % (first or "?")
    upper = " " + re.sub(r"\s+", " ", blanked).upper() + " "
    for bad in (" INTO ", " COPY ", " LOCK ", " FOR UPDATE", " FOR SHARE", " FOR NO KEY UPDATE", " FOR KEY SHARE"):
        if bad in upper:
            return "refused keyword: %s" % bad.strip()
    if first == "EXPLAIN" and " ANALYZE" in upper and not re.search(r"\bEXPLAIN\s*(\(.*\))?\s*(ANALYZE\s+)?(SELECT|WITH|VALUES|TABLE)\b", upper.strip()):
        return "EXPLAIN ANALYZE only over read statements"
    if first == "WITH" and re.search(r"\b(INSERT|UPDATE|DELETE|MERGE)\b", upper):
        return "data-modifying CTE"
    return None


if __name__ == "__main__":
    reason = check(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
    if reason:
        print("REFUSED: " + reason, file=sys.stderr)
        sys.exit(3)
