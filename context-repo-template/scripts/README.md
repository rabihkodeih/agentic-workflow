Small single-purpose helpers, one file, one job. Larger tools belong in `packages/`. Copied into cloned workspaces.

| Script | Does |
|---|---|
| `clone-ws.sh <src> <dst>` | copy a workspace (honouring `.cloneignore`, overlaying `.clone/` stubs), then `git init` + initial commit |
| `qa-lock.sh acquire\|check\|release\|status <stack> ...` | optional: atomic per-stack QA lock shared by all sessions on the machine; stale locks are taken over |
| `qa-stack.example.sh` | optional: skeleton for `qa-<stack>-stack.sh prepare\|restore`; copy and fill in per stack |
| `ci-babysit.sh <run-id> [repo-dir]` | poll a GitHub Actions run, rerun failed jobs, exit on green or after N reruns |
