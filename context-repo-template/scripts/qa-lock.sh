#!/usr/bin/env bash
# Local QA lock: one atomic mkdir lock per shared stack, across all sessions on the machine.
#
#   qa-lock.sh acquire <stack> <task> [worktree]    blocks, prints the token
#   qa-lock.sh check   <stack> <token>               exit 0 if the token holds it
#   qa-lock.sh release <stack> <token>               exit 0 if released or gone
#   qa-lock.sh status  <stack>
#
# Run acquire as a background shell so waiting costs no tokens. A lock is
# stale when its Claude session is gone or it exceeds QA_LOCK_MAX_AGE; the
# next waiter takes it over, which is safe because every run resets its QA state.
set -euo pipefail

ROOT="${QA_LOCK_ROOT:-${XDG_STATE_HOME:-$HOME/.local/state}/qa-locks}"
MAX_AGE="${QA_LOCK_MAX_AGE:-7200}"
POLL="${QA_LOCK_POLL:-20}"
GUARD_MAX_AGE=60

die() { echo "qa-lock: $*" >&2; exit 2; }

valid() { [[ "$1" =~ ^[A-Za-z0-9_-]+$ ]] || die "invalid name: $1"; }

meta() { sed -n "s/^$1=//p" "$LOCK/meta" 2>/dev/null | head -1; }

mtime() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1"; }

pid_start() { ps -o lstart= -p "$1" 2>/dev/null || true; }

# Nearest ancestor named claude, or 0 when run outside a session.
session_pid() {
  local pid=$$ comm
  [ -z "${QA_LOCK_SESSION_PID:-}" ] || { echo "$QA_LOCK_SESSION_PID"; return; }
  while [ -n "$pid" ] && [ "$pid" -gt 1 ]; do
    comm=$(ps -o comm= -p "$pid" 2>/dev/null || true)
    [ "${comm##*/}" = claude ] && { echo "$pid"; return; }
    pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
  done
  echo 0
}

# Prints why the lock is stale; prints nothing when it is free or healthy.
stale_reason() {
  [ -d "$LOCK" ] || return 0
  local now acquired pid
  now=$(date +%s)
  if [ ! -f "$LOCK/meta" ]; then
    [ $((now - $(mtime "$LOCK"))) -gt "$GUARD_MAX_AGE" ] && echo "no metadata"
    return 0
  fi
  acquired=$(meta acquired)
  pid=$(meta pid)
  if [ $((now - acquired)) -ge "$MAX_AGE" ]; then
    echo "over the ${MAX_AGE}s cap"
  elif [ "$pid" != 0 ] && [ "$(pid_start "$pid")" != "$(meta pid_start)" ]; then
    echo "session $pid is gone"
  fi
  return 0
}

# The guard stops two waiters from archiving a lock that was just re-taken.
reap() {
  local reason
  reason=$(stale_reason)
  [ -n "$reason" ] || return 0
  if [ -d "$LOCK.reap" ] &&
    [ $(($(date +%s) - $(mtime "$LOCK.reap"))) -gt "$GUARD_MAX_AGE" ]; then
    rmdir "$LOCK.reap" 2>/dev/null || true
  fi
  mkdir "$LOCK.reap" 2>/dev/null || return 0
  reason=$(stale_reason)
  if [ -n "$reason" ]; then
    echo "qa-lock: taking over $STACK lock from $(meta task): $reason" >&2
    mv "$LOCK" "$ROOT/history/$STACK-$(date +%s)-$$.stale"
  fi
  rmdir "$LOCK.reap"
}

acquire() {
  local task=$1 worktree=${2:-} pid start token
  valid "$task"
  pid=$(session_pid)
  start=$(pid_start "$pid")
  while :; do
    # An orphaned waiter must not take the lock for a dead session.
    if [ "$pid" != 0 ] && [ "$(pid_start "$pid")" != "$start" ]; then
      die "session $pid ended while waiting"
    fi
    reap
    if mkdir "$LOCK" 2>/dev/null; then
      token="$task-$(date +%s)-$$"
      {
        echo "token=$token"
        echo "task=$task"
        echo "worktree=$worktree"
        echo "pid=$pid"
        echo "pid_start=$start"
        echo "acquired=$(date +%s)"
      } >"$LOCK/meta.tmp"
      mv "$LOCK/meta.tmp" "$LOCK/meta"
      echo "$token"
      return 0
    fi
    sleep "$POLL"
  done
}

check() { [ -d "$LOCK" ] && [ "$(meta token)" = "$1" ] && [ -n "$1" ]; }

release() {
  local token=$1
  [ -d "$LOCK" ] || return 0
  if ! check "$token"; then
    # Taken over after a stale verdict: not ours to release.
    echo "qa-lock: $token does not hold $STACK (held by $(meta token))" >&2
    return 1
  fi
  mv "$LOCK" "$ROOT/history/$STACK-$token"
}

status() {
  if [ ! -d "$LOCK" ]; then
    echo "$STACK: free"
    return 0
  fi
  local reason
  reason=$(stale_reason)
  echo "$STACK: held by $(meta task) for $(($(date +%s) - $(meta acquired)))s" \
    "(worktree: $(meta worktree), session: $(meta pid))${reason:+, STALE: $reason}"
}

[ $# -ge 2 ] || die "usage: qa-lock.sh acquire|check|release|status <stack> [...]"
CMD=$1
STACK=$2
shift 2
valid "$STACK"
mkdir -p "$ROOT/history"
LOCK="$ROOT/$STACK.lock"

case "$CMD" in
  acquire) [ $# -ge 1 ] || die "acquire needs a task"; acquire "$@" ;;
  check) [ $# -eq 1 ] || die "check needs a token"; check "$1" ;;
  release) [ $# -eq 1 ] || die "release needs a token"; release "$1" ;;
  status) status ;;
  *) die "unknown command: $CMD" ;;
esac
