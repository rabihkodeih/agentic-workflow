---
name: prod-db-postgres
description: Run read-only SQL against a production Postgres (private RDS) over a per-call SSM port-forward through a running instance in the VPC. Use when the user asks to query, count, inspect or check data in "the prod DB", "prod RDS" or "the production database" and wants a number the analytics replica cannot give. Read-only: SELECT/WITH/VALUES/SHOW/EXPLAIN/TABLE and psql describe commands only, enforced client-side and server-side.
---

# Production Postgres, read-only queries

One call = one throwaway session: SSO check → DB URL from SSM (never printed) →
find a running instance by tag → SSM port-forward on a free local port → `psql`
with the session forced read-only → tunnel torn down. Nothing stays open between
calls, so nothing can go stale.

```bash
scripts/query.sh 'SELECT count(*) FROM orders WHERE status = 1'
scripts/query.sh --format json 'SELECT id, name, enabled FROM routes ORDER BY id'
scripts/query.sh --format csv --limit 0 'SELECT ...' > out.csv
scripts/query.sh 'SELECT 1' 'SELECT 2'          # several statements, one tunnel
scripts/query.sh '\dt public.*' '\d+ orders'    # psql describe meta-commands
```

`scripts/query.sh --help` is the full reference. Double-quote SQL that contains
`'string literals'`.

Flags: `--format table|json|csv` (default `table`) · `--limit N` printed rows for
SELECT/WITH (default 200, `0` = no cap; applied by wrapping the statement in
`SELECT * FROM (...) LIMIT N`) · `--timeout SECONDS` server-side statement timeout
(default 60) · `--profile` AWS profile.

Exit codes: `1` preflight/tunnel · `2` psql error · `3` statement refused · `4` timed out.

## Configuration

Set once, in the environment or in `scripts/config.env` (sourced if present, gitignored):

| Variable | What |
|---|---|
| `PRODDB_AWS_PROFILE` | AWS SSO profile with SSM and EC2 describe rights |
| `PRODDB_AWS_REGION` | region of the instance and the parameter |
| `PRODDB_SSM_DB_URL_PARAM` | SSM SecureString holding `postgres://user:pass@host:port/db` |
| `PRODDB_INSTANCE_TAG` | `Name` tag of an instance inside the VPC that can reach the DB |

Copy `scripts/config.example.env` to `scripts/config.env` and fill it in.

## Ask the user before the first query of a session

This is the live production database. Confirm with the user before the first
query, and again for anything that is not a cheap indexed lookup: an unbounded scan
competes with the web and worker tiers for the same instance. Cheap follow-ups in
an already-authorised session do not each need a fresh confirmation. When the
harness blocks the command, hand the exact command to the user to run themselves.

## Look, do not guess

`\dt <pattern>` and `\d+ <table>` cost nothing. Use them before writing SQL against
a table you have not seen. Keep a short schema cheat sheet in the project's
`domain-knowledge.md`, dated, and refresh it when it is wrong.

## How read-only is enforced

1. `scripts/guard.py` allow-lists the statement (`SELECT`/`WITH`/`VALUES`/`SHOW`/
   `EXPLAIN`/`TABLE`, one per call, describe meta-commands only), refuses `INTO`,
   `COPY`, `LOCK`, `FOR UPDATE` and data-modifying CTEs. Literals and comments are
   blanked first so a `;` inside quotes is not misread. Offline tests:
   `python3 scripts/test_guard.py`.
2. `PGOPTIONS="-c default_transaction_read_only=on"`: the server rejects any write.
   This is the layer that holds.
3. `statement_timeout` (`--timeout`) and the printed-row cap.

## Why it cannot just connect

The RDS instance is private to the VPC. The script port-forwards through a running
instance with `AWS-StartPortForwardingSessionToRemoteHost`; the credentials come
from the SSM parameter and stay in the script's environment. Instance replacement
by an autoscaling group is harmless (discovered by tag every call), and so is a
credential rotation (read every call).

## Failure modes

| Symptom | Meaning |
|---|---|
| `SSO token expired or missing for profile X. Run: aws sso login --profile X` | Browser SSO; the user must run it |
| `no running <tag> instance found` | Wrong profile/region, or the ASG is mid-refresh; retry in a minute |
| `port-forward ... did not come up` / `SSM session died` | session-manager-plugin missing, or the instance's SSM agent is unhealthy |
| `REFUSED: ...` (exit 3) | Not read-only. Do not reword around the guard |
| `REFUSED by server: read-only session` | Something got past the guard; the server stopped it |
| `TIMEOUT: exceeded Ns` (exit 4) | Narrow the query (date range, indexed columns) before raising `--timeout` |

Requirements on macOS: `aws` CLI v2 with an SSO profile, `session-manager-plugin`
(`brew install --cask session-manager-plugin`), `psql` (`brew install libpq`),
`python3`, `nc`.

## Extension point

Encrypted columns (Fernet, KMS envelope, whatever the app uses) come back as
ciphertext. Add a `--decrypt col,col` flag that pipes the JSON result through a
small script running under the application's own key loader. Keys stay in that
process; decrypted rows are production PII and go to a scratch directory, never a repo.
