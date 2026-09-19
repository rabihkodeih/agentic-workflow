---
name: prod-db-mysql-bastion
description: Run read-only SQL against a production MySQL/Aurora database that has no public endpoint (RDS Proxy inside a VPC), by piping a small runner to an EC2 instance in that VPC over SSH-via-SSM and executing it there. Use when the user asks to query, inspect, count or check data in "the production database" and the DB is only reachable from inside the VPC. Read-only: SELECT/SHOW/DESCRIBE/EXPLAIN only, enforced server-side.
---

# Production MySQL behind a VPC, read-only queries

Runs one read-only statement against prod and returns the rows.

```bash
scripts/query.sh 'SELECT COUNT(*) AS dealers FROM company'
scripts/query.sh --format json 'SELECT id, name FROM company LIMIT 20'
scripts/query.sh --timeout 60 'SELECT ... a slower analytical query ...'
```

Flags: `--format table|json` (default `table`) · `--limit N` (default 200) ·
`--timeout SECONDS` (default 30) · `--start` (boot the instance if it is stopped).

## Configuration

Env or `scripts/config.env` (sourced if present, gitignored). Copy `config.example.env`.

| Variable | What |
|---|---|
| `BASTION_INSTANCE_ID` | EC2 inside the VPC whose instance role may read the DB secret |
| `BASTION_SSH_ALIAS` | `~/.ssh/config` host using `ProxyCommand aws ssm start-session ... AWS-StartSSHSession` |
| `BASTION_AWS_PROFILE` / `BASTION_AWS_REGION` | SSO profile and region |
| `BASTION_REMOTE_PYTHON` | a python on the instance with `pymysql` and `boto3` |
| `DB_SECRET_ID`, `DB_HOST`, `DB_PORT`, `DB_NAME` | Secrets Manager id and the proxy endpoint, sent to the runner |

Hardcode `DB_HOST` in `config.env` for one environment on purpose: a skill that can be
pointed at any host by an env var an operator last set is not prod-only by construction.

## Schema: look, do not guess

`SHOW TABLES` and `DESCRIBE <table>` cost a few milliseconds. Start there instead of
assuming a name, and keep a dated cheat sheet in the project's `domain-knowledge.md`.

## Ask the user before the first query of a session

This hits a live production database. Confirm with the user before the first query,
and again for anything that is not a cheap indexed lookup: a wide scan on prod
competes with the real pipeline for proxy connections. Cheap `COUNT(*)` follow-ups in
an already-authorised session do not each need a fresh confirmation.

## Why it cannot just connect

The RDS Proxy has no public endpoint, so the laptop cannot reach it. `query.sh` pipes
`runner.py` to the instance over SSH-via-SSM and it executes there. DB credentials are
read from Secrets Manager by the instance role, so no password ever reaches the
caller's machine or the transcript.

## How read-only is enforced

The DB user may well have full privileges (many shops have no read-only role), so
read-only is enforced by the skill, in three layers:

1. Statement allow-list: `SELECT` / `WITH` / `SHOW` / `DESCRIBE` / `EXPLAIN`, one
   statement per call. String literals and comments are blanked before the check, so a
   `;` inside `'...'` is not misread as a stacked statement.
2. No-file-write check: rejects `INTO OUTFILE` / `INTO DUMPFILE` (a `SELECT` that writes).
3. `START TRANSACTION READ ONLY`: the server rejects any write with error 1792. This is
   the layer that holds; 1 and 2 exist to fail fast with a clear message.

Plus `max_execution_time` (default 30s) and a row cap, which is the guard that matters
day to day: on a live cluster the real hazard is an unbounded join pinning a proxy
connection, not a rogue `DELETE`.

`scripts/test_guard.py` covers the guard offline (no DB, no AWS): `python3 scripts/test_guard.py`.

## Failure modes

| Symptom | Meaning |
| --- | --- |
| `SSO token expired. Run: aws sso login --profile X` | The user must log in; you cannot do it for them |
| `instance is 'stopped'` | Ask the user, then re-run with `--start` (a small instance costs a few dollars a month running, nothing stopped) |
| `SSM agent is ConnectionLost` | Box is running but saturated; the agent got starved off the network. Common right after `--start` following a long stop when missed cron timers fire at boot. Wait for CPU to drop, or reboot |
| `REFUSED: ...` (exit 3) | The statement is not read-only. Do not try to reword around the guard |
| `TIMEOUT: ...` (exit 4) | Query exceeded `--timeout` and was killed server-side. Narrow it before raising the limit |
| `No such file or directory: <remote python>` | Point `BASTION_REMOTE_PYTHON` at a venv on the instance with `pymysql` and `boto3` |

pymysql TLS quirk: `ssl={"ca": None}`, not `{}`, is the shape that triggers the TLS
path; an RDS Proxy rejects a plaintext connection (error 3159).
