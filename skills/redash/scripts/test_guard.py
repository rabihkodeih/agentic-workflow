#!/usr/bin/env python3
"""Offline check of the read-only guard, no network, no API key."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redash  # noqa: E402

ALLOW = [
    "SELECT 1",
    "  select * from t where name = 'a; drop table x'",
    "WITH c AS (SELECT 1) SELECT * FROM c",
    "(SELECT 1)",
    "SHOW TABLES",
    "DESCRIBE company",
    "EXPLAIN SELECT * FROM t",
    "SELECT 1; -- trailing comment only",
    "SELECT '--not a comment' FROM t",
]

REFUSE = [
    "DELETE FROM t",
    "UPDATE t SET a = 1",
    "INSERT INTO t VALUES (1)",
    "DROP TABLE t",
    "TRUNCATE t",
    "GRANT ALL ON x TO y",
    "SELECT * FROM t INTO OUTFILE '/tmp/x'",
    "SELECT 1; DELETE FROM t",
    "-- SELECT 1\nDELETE FROM t",
    "/* select */ DELETE FROM t",
    "CREATE TABLE t (a int)",
]

failed = 0
for sql in ALLOW:
    try:
        redash.assert_read_only(sql)
    except SystemExit:
        print("FAIL (should allow): %r" % sql)
        failed += 1

for sql in REFUSE:
    try:
        redash.assert_read_only(sql)
        print("FAIL (should refuse): %r" % sql)
        failed += 1
    except SystemExit:
        pass

print("%d/%d cases passed" % (len(ALLOW) + len(REFUSE) - failed, len(ALLOW) + len(REFUSE)))
sys.exit(1 if failed else 0)
