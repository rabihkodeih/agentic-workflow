#!/usr/bin/env bash
# Run one read-only SQL statement against a production MySQL that has no public endpoint.
#
# Pipes runner.py to an EC2 inside the VPC over SSH-via-SSM and runs it there; credentials
# are read from Secrets Manager by the instance role and never reach this machine.
#
#   query.sh 'SELECT COUNT(*) FROM company'
#   query.sh --format json 'SELECT id, name FROM company LIMIT 5'
#   echo 'SELECT 1' | query.sh
#
# Exit codes: 1 preflight failed · 3 statement refused (not read-only) · 4 query timed out
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/config.env" ]] && source "$SCRIPT_DIR/config.env"
INSTANCE_ID="${BASTION_INSTANCE_ID:-}"
SSH_ALIAS="${BASTION_SSH_ALIAS:-}"
PROFILE="${BASTION_AWS_PROFILE:-}"
REGION="${BASTION_AWS_REGION:-}"
REMOTE_PYTHON="${BASTION_REMOTE_PYTHON:-python3}"

FORMAT="table"
LIMIT=200
TIMEOUT=30
START_IF_STOPPED=0
SQL=""

die() { echo "error: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --format)  FORMAT="$2"; shift 2 ;;
    --limit)   LIMIT="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --start)   START_IF_STOPPED=1; shift ;;
    -*)        die "unknown flag: $1" ;;
    *)         SQL="$1"; shift ;;
  esac
done

[[ -n "$SQL" ]] || SQL="$(cat)"          # fall back to stdin
[[ -n "${SQL// /}" ]] || die "no SQL given"
[[ "$FORMAT" == "table" || "$FORMAT" == "json" ]] || die "--format must be table or json"
for v in INSTANCE_ID SSH_ALIAS PROFILE REGION DB_SECRET_ID DB_HOST DB_NAME; do
  [[ -n "${!v:-}" ]] || die "$v is not set (see scripts/config.example.env)"
done
export AWS_PROFILE="$PROFILE" AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"

# --- preflight 1: AWS credentials ------------------------------------------------
aws sts get-caller-identity --query Account --output text >/dev/null 2>&1 \
  || die "SSO token expired. Run: aws sso login --profile $PROFILE"

# --- preflight 2: the EC2 must be running ----------------------------------------
STATE="$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
          --query 'Reservations[].Instances[].State.Name' --output text)"
if [[ "$STATE" != "running" ]]; then
  if [[ "$START_IF_STOPPED" -eq 0 ]]; then
    die "instance $INSTANCE_ID is '$STATE'. Re-run with --start to boot it."
  fi
  echo "starting $INSTANCE_ID (was $STATE)..." >&2
  aws ec2 start-instances --instance-ids "$INSTANCE_ID" >/dev/null
fi

# --- preflight 3: SSM agent must be Online (lags EC2 'running' by 30-60s) ---------
# `ConnectionLost` is NOT "still booting": the agent was up and stopped answering,
# usually because CPU load starved it. Report it instead of spinning for 5 minutes.
for _ in $(seq 24); do
  PING="$(aws ssm describe-instance-information \
           --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
           --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null || true)"
  [[ "$PING" == "Online" ]] && break
  [[ "$PING" == "ConnectionLost" ]] && die \
    "SSM agent is ConnectionLost on $INSTANCE_ID (instance is running). Check CPUUtilization;
       wait for the load to drop, or reboot: aws ec2 reboot-instances --instance-ids $INSTANCE_ID"
  sleep 5
done
[[ "${PING:-}" == "Online" ]] || die "SSM agent never came Online for $INSTANCE_ID (last status: ${PING:-none})"

# base64 so the request crosses the remote shell as one opaque token, no quoting hazards.
PAYLOAD="$(SQL="$SQL" FORMAT="$FORMAT" LIMIT="$LIMIT" TIMEOUT="$TIMEOUT" python3 -c '
import base64, json, os
print(base64.b64encode(json.dumps({
    "sql": os.environ["SQL"],
    "format": os.environ["FORMAT"],
    "limit": int(os.environ["LIMIT"]),
    "timeout": int(os.environ["TIMEOUT"]),
    "secret_id": os.environ["DB_SECRET_ID"],
    "host": os.environ["DB_HOST"],
    "port": int(os.environ.get("DB_PORT", "3306")),
    "database": os.environ["DB_NAME"],
    "region": os.environ["AWS_REGION"],
}).encode()).decode())')"

exec ssh -o ConnectTimeout=30 "$SSH_ALIAS" "$REMOTE_PYTHON - '$PAYLOAD'" < "$SCRIPT_DIR/runner.py"
