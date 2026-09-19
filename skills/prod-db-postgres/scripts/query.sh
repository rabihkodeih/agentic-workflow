#!/usr/bin/env bash
# prod-db-postgres: read-only SQL against a private production Postgres over SSM.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/config.env" ]] && source "$SCRIPT_DIR/config.env"
PROFILE="${PRODDB_AWS_PROFILE:-}"
REGION="${PRODDB_AWS_REGION:-}"
SSM_DB_URL_PARAM="${PRODDB_SSM_DB_URL_PARAM:-}"
INSTANCE_TAG="${PRODDB_INSTANCE_TAG:-}"
PSQL="${PSQL_BIN:-/opt/homebrew/opt/libpq/bin/psql}"

FORMAT="table"; LIMIT=200; TIMEOUT=60
STATEMENTS=()

usage() {
cat <<'HELP'
prod-db-postgres: run read-only SQL against a private production Postgres through a
per-call SSM port-forward. No VPN, no bastion key.

USAGE
  query.sh [flags] '<sql>' ['<sql>' ...]
  echo '<sql>' | query.sh [flags]

FLAGS
  --format table|json|csv   Output format (default: table).
  --limit N                 Cap printed rows for SELECT/WITH/VALUES/TABLE (default 200,
                            0 = no cap). The cap trims what is printed, not what the DB
                            computes; put your own LIMIT in the SQL for big scans.
  --timeout SECONDS         Server-side statement_timeout (default 60). Exit 4 when hit.
  --profile NAME            AWS profile (default: $PRODDB_AWS_PROFILE).
  -h, --help                This text.

CONFIG (env or scripts/config.env)
  PRODDB_AWS_PROFILE  PRODDB_AWS_REGION  PRODDB_SSM_DB_URL_PARAM  PRODDB_INSTANCE_TAG

WHAT ONE CALL DOES
  1. Guards every statement client-side (scripts/guard.py). Refusals exit 3 before
     any AWS call.
  2. Checks the SSO token (aws sts get-caller-identity).
  3. Reads the DB URL from SSM into the environment (never printed), finds a running
     instance by tag, opens an SSM port-forward on a free local port.
  4. Runs psql with PGOPTIONS forcing default_transaction_read_only=on (the SERVER
     rejects writes) and statement_timeout. Several statements share one tunnel.
  5. Tears the tunnel down on exit.

EXIT CODES
  0 ok · 1 preflight or tunnel failed · 2 psql error · 3 statement refused · 4 timed out
HELP
}

die() { echo "error: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --format)  FORMAT="$2"; shift 2 ;;
    --limit)   LIMIT="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --)        shift; STATEMENTS+=("$@"); break ;;
    -*)        die "unknown flag: $1 (see --help)" ;;
    *)         STATEMENTS+=("$1"); shift ;;
  esac
done
[[ ${#STATEMENTS[@]} -gt 0 ]] || STATEMENTS=("$(cat)")
[[ "$FORMAT" =~ ^(table|json|csv)$ ]] || die "--format must be table, json or csv"
[[ "$LIMIT" =~ ^[0-9]+$ && "$TIMEOUT" =~ ^[0-9]+$ ]] || die "--limit/--timeout must be integers"
for v in PROFILE REGION SSM_DB_URL_PARAM INSTANCE_TAG; do
  [[ -n "${!v}" ]] || die "$v is not set (see --help, CONFIG)"
done

# 1. Guard every statement before touching AWS.
for SQL in "${STATEMENTS[@]}"; do
  python3 "$SCRIPT_DIR/guard.py" "$SQL" || exit 3
done

# 2. Preflight.
command -v aws >/dev/null || die "aws CLI not found"
command -v session-manager-plugin >/dev/null || die "session-manager-plugin not found (brew install --cask session-manager-plugin)"
[[ -x "$PSQL" ]] || PSQL="$(command -v psql || true)"
[[ -x "${PSQL:-/nonexistent}" ]] || die "psql not found (brew install libpq)"
export AWS_PROFILE="$PROFILE" AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  die "SSO token expired or missing for profile $PROFILE. Run: aws sso login --profile $PROFILE"
fi

# 3. DB URL from SSM -> env only; instance by tag.
URL="$(aws ssm get-parameter --name "$SSM_DB_URL_PARAM" --with-decryption --query Parameter.Value --output text 2>/dev/null)" \
  || die "could not read $SSM_DB_URL_PARAM from SSM"
eval "$(python3 - "$URL" <<'PY'
import sys, shlex
from urllib.parse import urlsplit, unquote
u = urlsplit(sys.argv[1])
print("RHOST=%s RPORT=%s PGDATABASE=%s PGUSER=%s PGPASSWORD=%s" % (
    shlex.quote(u.hostname or ""), u.port or 5432, shlex.quote(u.path.lstrip("/")),
    shlex.quote(unquote(u.username or "")), shlex.quote(unquote(u.password or ""))))
PY
)"
unset URL
export PGDATABASE PGUSER PGPASSWORD
IID="$(aws ec2 describe-instances --filters Name=tag:Name,Values="$INSTANCE_TAG" Name=instance-state-name,Values=running \
        --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null)"
[[ -n "$IID" && "$IID" != "None" ]] || die "no running $INSTANCE_TAG instance found"

# 4. Free local port + SSM port-forward, torn down on exit.
LP="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
aws ssm start-session --target "$IID" --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "host=$RHOST,portNumber=$RPORT,localPortNumber=$LP" >/dev/null 2>&1 &
SP=$!
trap 'kill $SP 2>/dev/null; wait $SP 2>/dev/null' EXIT
for _ in $(seq 1 40); do nc -z 127.0.0.1 "$LP" 2>/dev/null && break; kill -0 $SP 2>/dev/null || die "SSM session died (is $IID reachable?)"; sleep 0.5; done
nc -z 127.0.0.1 "$LP" 2>/dev/null || die "port-forward to $RHOST:$RPORT did not come up"

# 5. Run: session read-only + statement timeout, enforced by the server.
export PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=$((TIMEOUT * 1000))"
export PGCONNECT_TIMEOUT=15
STATUS=0
for SQL in "${STATEMENTS[@]}"; do
  RAW="$(printf '%s' "$SQL" | sed -e 's/[[:space:]]*$//' -e 's/;$//')"
  FIRST="$(printf '%s' "$RAW" | sed -e 's/^[[:space:]]*//' | cut -c1-6 | tr '[:lower:]' '[:upper:]')"
  WRAPPABLE=0; case "$FIRST" in SELECT*|WITH*|VALUES*|TABLE*) WRAPPABLE=1 ;; esac
  [[ "$RAW" == \\* ]] && WRAPPABLE=0
  if [[ $WRAPPABLE -eq 1 && "$LIMIT" -gt 0 ]]; then RUN="SELECT * FROM ($RAW) _q LIMIT $LIMIT"; else RUN="$RAW"; fi
  if [[ $WRAPPABLE -eq 1 && "$FORMAT" == "json" ]]; then
    RUN="SELECT COALESCE(json_agg(_j), '[]'::json) FROM ($RUN) _j"; ARGS=(-At)
  elif [[ "$FORMAT" == "csv" ]]; then ARGS=(--csv)
  else ARGS=(); fi
  [[ ${#STATEMENTS[@]} -gt 1 ]] && printf '== %s\n' "$(printf '%s' "$RAW" | cut -c1-160)"
  OUT="$("$PSQL" -h 127.0.0.1 -p "$LP" -X -v ON_ERROR_STOP=1 "${ARGS[@]}" -c "$RUN" 2>&1)"; RC=$?
  printf '%s\n' "$OUT"
  if [[ $RC -ne 0 ]]; then
    if printf '%s' "$OUT" | grep -q "statement timeout"; then echo "TIMEOUT: exceeded ${TIMEOUT}s (raise --timeout or narrow the query)" >&2; STATUS=4
    elif printf '%s' "$OUT" | grep -q "read-only transaction"; then echo "REFUSED by server: read-only session" >&2; STATUS=3
    else STATUS=2; fi
  fi
done
exit $STATUS
