#!/usr/bin/env bash
# Skeleton for a QA stack script. Copy to qa-<stack>-stack.sh, set STACK, fill in prepare and restore.
#
#   qa-<stack>-stack.sh prepare <token> <worktree>   fresh QA state from a clean baseline, serve the worktree
#   qa-<stack>-stack.sh restore [token]              back to the main checkout and baseline state
#
# Hold the lock first (qa-lock.sh). restore runs before release; without a token it only runs while the lock is free.
set -euo pipefail

STACK=example
HERE=$(cd "$(dirname "$0")" && pwd)
LOCK="$HERE/qa-lock.sh"

die() { echo "qa-$STACK-stack: $*" >&2; exit 2; }
say() { echo "[$(date +%H:%M:%S)] $*"; }

need_lock() { "$LOCK" check "$STACK" "$1" || die "token $1 does not hold the $STACK lock"; }

prepare() {
  local token=$1 worktree=$2
  need_lock "$token"
  [ -d "$worktree" ] || die "no worktree: $worktree"
  say "preparing $STACK for $worktree"
  # 1. Recreate QA data from the baseline (never modify the baseline itself).
  # 2. Apply the branch's migrations.
  # 3. Point the running services at $worktree and wait until they answer.
  die "prepare not implemented"
}

restore() {
  if [ -n "${1:-}" ]; then
    need_lock "$1"
  else
    "$LOCK" status "$STACK" | grep -q ': free$' || die "lock is held; pass its token"
  fi
  say "restoring $STACK"
  # Point services back at the main checkout and baseline data; wait until they answer.
  die "restore not implemented"
}

case "${1:-}" in
  prepare) [ $# -eq 3 ] || die "usage: prepare <token> <worktree>"; prepare "$2" "$3" ;;
  restore) restore "${2:-}" ;;
  *) die "usage: $(basename "$0") prepare <token> <worktree> | restore [token]" ;;
esac
