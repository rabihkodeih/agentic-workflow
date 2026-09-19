"""Offline tests for the read-only guard, no DB, no AWS, no network.

    python3 test_guard.py

The guard is the skill's safety boundary for everything except an actual write
(which the server's READ ONLY transaction rejects), so it is worth testing the
adversarial cases: a semicolon inside a string literal or comment must NOT be
mistaken for a stacked statement, and `SELECT ... INTO OUTFILE` must be caught
even though it starts with SELECT.
"""

import importlib.util
import pathlib
import sys

spec = importlib.util.spec_from_file_location(
    "runner", pathlib.Path(__file__).with_name("runner.py")
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

CASES = [
    ("SELECT 1", True),
    ("select id from company limit 5", True),
    ("SELECT 1;", True),
    ("WITH t AS (SELECT 1 AS a) SELECT * FROM t", True),
    ("SHOW TABLES", True),
    ("DESCRIBE company", True),
    ("EXPLAIN SELECT * FROM company", True),
    ("SELECT '; DROP TABLE company' AS s", True),
    ("SELECT 1 -- ; DROP TABLE company", True),
    ("SELECT 1 /* ; DROP TABLE company */", True),
    ("SELECT 1; DROP TABLE company", False),
    ("DELETE FROM company", False),
    ("UPDATE company SET name='x'", False),
    ("INSERT INTO company VALUES (1)", False),
    ("DROP TABLE company", False),
    ("TRUNCATE company", False),
    ("GRANT ALL ON *.* TO 'x'@'%'", False),
    ("SELECT * INTO OUTFILE '/tmp/x' FROM company", False),
    ("select * into dumpfile '/tmp/x' from company", False),
    ("", False),
    ("   ", False),
]

if __name__ == "__main__":
    failures = 0
    for sql, should_pass in CASES:
        try:
            runner.guard(sql)
            allowed, why = True, ""
        except ValueError as exc:
            allowed, why = False, str(exc)
        ok = allowed == should_pass
        failures += not ok
        verdict = "ok  " if ok else "FAIL"
        print(f"{verdict} {'allow' if should_pass else 'block':5} {sql[:42]!r:46} {why}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    sys.exit(1 if failures else 0)
