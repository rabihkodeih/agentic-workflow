#!/usr/bin/env python3
"""Offline tests for guard.py (no DB, no AWS): python3 scripts/test_guard.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guard import check

OK = [
    "SELECT 1",
    "select count(*) from orders where status = 'a; DROP'",
    "WITH x AS (SELECT 1) SELECT * FROM x",
    "EXPLAIN SELECT 1",
    "EXPLAIN (ANALYZE, BUFFERS) SELECT 1",
    "SHOW server_version",
    "TABLE routes",
    "select $$; into $$ as s",
    "select 1 -- into outfile\n",
    "select 1 /* ; */",
    "\\dt public.*",
    "\\d+ orders",
    "\\l",
    "select 1;",
]
REFUSED = [
    "DELETE FROM orders",
    "UPDATE t SET a=1",
    "INSERT INTO t VALUES (1)",
    "SELECT 1; SELECT 2",
    "SELECT * INTO newtable FROM t",
    "COPY t TO '/tmp/x'",
    "WITH d AS (DELETE FROM t RETURNING *) SELECT * FROM d",
    "SELECT * FROM t FOR UPDATE",
    "LOCK TABLE t",
    "\\! rm -rf /",
    "\\copy t to '/tmp/x'",
    "",
    "TRUNCATE t",
    "EXPLAIN ANALYZE DELETE FROM t",
]
fails = 0
for sql in OK:
    r = check(sql)
    if r: fails += 1; print("should ALLOW:", repr(sql), "->", r)
for sql in REFUSED:
    r = check(sql)
    if not r: fails += 1; print("should REFUSE:", repr(sql))
print("guard tests:", "OK" if not fails else "%d FAILED" % fails)
sys.exit(1 if fails else 0)
