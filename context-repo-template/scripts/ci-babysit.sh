#!/usr/bin/env bash
# ci-babysit.sh <run-id> [repo-dir]: poll a GitHub Actions run; on failure rerun failed jobs.
# Exits 0 on success, 1 after CI_BABYSIT_MAX_RERUNS reruns (default 10). Run it as a background shell.
set -u
RUN=${1:?usage: ci-babysit.sh <run-id> [repo-dir]}
cd "${2:-.}" || exit 2
MAX=${CI_BABYSIT_MAX_RERUNS:-10}
RERUNS=0
while true; do
  st=$(gh run view "$RUN" --json status --jq .status)
  if [ "$st" = "completed" ]; then
    c=$(gh run view "$RUN" --json conclusion --jq .conclusion)
    echo "$(date -u +%H:%M) completed: $c"
    if [ "$c" = "success" ]; then echo ALL_GREEN; exit 0; fi
    [ "$RERUNS" -ge "$MAX" ] && { echo GIVING_UP; exit 1; }
    gh run view "$RUN" --json jobs --jq '.jobs[]|select(.conclusion=="failure")|"  red: \(.name)"'
    gh run rerun "$RUN" --failed 2>&1 && { RERUNS=$((RERUNS + 1)); echo "  rerun #$RERUNS triggered"; }
    sleep 60
  fi
  sleep 30
done
