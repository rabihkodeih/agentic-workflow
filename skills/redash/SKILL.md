---
name: redash
description: Query a Redash instance over its REST API , list data sources and saved queries, read a saved query's SQL, run it, or run ad-hoc read-only SQL and get the rows back. Use when the user asks about Redash, a Redash query/dashboard/link, "run that query", "what does query 1234 return", or wants numbers out of an analytics data source rather than the application DB.
---

# Redash, query over the API

`scripts/redash.py` talks to the Redash REST API with a user API key. Python stdlib
only, no venv, no pip.

```bash
scripts/redash.py whoami                      # verify the key works
scripts/redash.py datasources                 # -> ids you need for `query`
scripts/redash.py queries "lead routing"      # search saved queries
scripts/redash.py get 1234                    # show that query's SQL + parameters
scripts/redash.py run 1234 --param dealer_id=42
scripts/redash.py query 'SELECT count(*) FROM leads' -d 3
scripts/redash.py query - -d 3 < /tmp/big.sql
scripts/redash.py dashboard my-dashboard-slug # widget -> query id map
scripts/redash.py raw /api/users              # any endpoint not wrapped above
```

Shared flags on `run`/`query`: `--format table|json|csv` (default `table`) ·
`--limit N` printed rows (default 200) · `--width N` column truncation (default 48) ·
`--timeout S` how long to wait for the job (default 180) · `--max-age S` accept a
cached result younger than S seconds (default 0 = always execute fresh) ·
`--param key=value` (repeatable; values that parse as JSON are sent as JSON).

## Setup, one time, key never enters the transcript

Set `REDASH_URL` to the instance's base URL (env, or `~/.config/redash/url`). The user
gets the key from `<REDASH_URL>/users/me` (Account → API Key) and stores it themselves:

```bash
security add-generic-password -a "$USER" -s redash-api-key -w
```

(paste at the prompt, press enter). Resolution order is `$REDASH_API_KEY` → that
keychain item → `~/.config/redash/api.key`. **Never ask the user to paste the
key into chat, and never echo it.**

## Data sources

Run `datasources` once per session and keep the ids you use in the project's
`domain-knowledge.md`, dated. Ids differ per instance and drift over time.

## How it runs a query

Redash executes asynchronously: the POST returns a job, and the script polls
`/api/jobs/<id>` until status 3 (success), then fetches `/api/query_results/<id>`. On
`--timeout` it cancels the job rather than orphaning it. A saved query with
parameters will fail server-side if a required `--param` is missing , run `get` first
to see the parameter names.

## Prefer a saved query over hand-written SQL

Someone has usually already written it. `queries <search>` then `get <id>` is cheaper
and less wrong than inventing SQL against a schema you have not read. When you do go
ad-hoc, `schema <data_source_id> --grep <fragment>` first , guessing table names
against an analytics warehouse wastes a round trip each time.

## Read-only by default

`query` refuses anything that isn't `SELECT` / `WITH` / `SHOW` / `DESCRIBE` /
`EXPLAIN`, rejects `INTO OUTFILE`/`DUMPFILE`, and allows one statement per call.
String literals and comments are blanked before the check, so a `;` or a keyword
inside quotes can't slip past. `--unsafe` skips the guard, only with an explicit
instruction from the user, since a Redash data source may well be pointed at a
writable production database.

The guard is covered offline (no key, no network): `python3 scripts/test_guard.py`.

Volume matters more than write risk day to day: `--limit` only trims what is
*printed*, the warehouse still computes the full result. Put the `LIMIT` in the SQL
for exploratory work.

## Failure modes

| Symptom | Meaning |
| --- | --- |
| `NO API KEY` | Nothing in env/keychain/keyfile; do the Setup step above |
| `AUTH: ... 403 ... error_code 1010 browser_signature_banned` | **Not** a key problem: Cloudflare in front of the host bans the default `Python-urllib` User-Agent before the key is read. The script already sends a browser UA; if Cloudflare tightens again, override with `$REDASH_USER_AGENT` |
| `AUTH: Redash returned 401/403` (no `cloudflare_error`) | Key revoked, or the user's Redash groups don't grant that data source/query |
| `Non-JSON reply` | An SSO/proxy login page came back instead of the API , the user needs to re-auth in the browser |
| `QUERY FAILED: ...` | The data source rejected the SQL; the message is verbatim from the DB |
| `TIMEOUT: ...` | Job cancelled after `--timeout`; narrow the query before raising it |
