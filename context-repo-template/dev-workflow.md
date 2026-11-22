# Development workflow

> Loaded in every session started in this workspace through `CLAUDE.md`. For sessions started inside a sibling repo, symlink the shared parent's `CLAUDE.md` to this file (`ln -s <workspace>/dev-workflow.md <parent>/CLAUDE.md`) and drop the `@dev-workflow.md` line from the workspace's `CLAUDE.md` so it isn't loaded twice. Keep this file free of `@` imports. In a workspace family, edit only the root's copy; clones carry a snapshot.

Purpose: coding sessions progress autonomously, several at once if needed. Applies to code changes in any package or repo listed in `AGENTS.md` "Code". Tuned for personal and research projects: lightweight by default, heavier steps only where the project opts in.

Precedence: this file overrides the git defaults in `AGENTS.md` (who commits and pushes) and allows the commit, push and optional PR actions below. Any other, stricter rule in `AGENTS.md` wins (e.g. a read-only workspace does no coding and no outward actions).

## Default task workflow
Use for every task handed over unless told otherwise; with several tasks, run one pipeline per task in parallel. Task id: the issue key when a tracker is used (`proj_123`), else a short slug.
Skip what doesn't apply (no remote → no push; no CI → skip G; no tracker → skip I) and say in the report which steps were skipped and why.
- **A.** Side branch named after the task only, e.g. `fix-login-timeout`, in its own worktree (see Branches and worktrees).
- **B.** Scope + unit tests via the coder / unit-test-writer pair (see TDD).
- **C.** Once B is fully done: subagent code review of the diff against the base; fix what's worth fixing, re-run the unit tests.
- **D.** Lint and type-check with whatever the package or repo has configured. If a tool can't run, say so and continue.
- **E.** Run it for real once: the CLI, script, notebook or example that exercises the change. Report what was observed. A full QA run happens only if `AGENTS.md` "Code" declares a QA stack (see Optional: shared-stack QA).
- **F.** Finish: commit on the task branch and push it if there is a remote (see Finishing). No PR unless the repo opts in.
- **G.** CI green on the pushed branch, if the repo has CI; rerun flakes (`scripts/ci-babysit.sh`), fix real failures.
- **H.** Stop and report; the human merges the branch into main, or tells the agent to.
- **I.** Post-merge tracker steps, only those listed in `AGENTS.md` "Issue tracker".

## Branches and worktrees
- Default: all work lands on main, through side branches that are merged when ready. A branch can stay open as long as it is useful.
- A small change with no parallel session may be committed straight on main, in the main checkout, when the human asks for it or `AGENTS.md` "Code" allows it for that repo; say so.
- One worktree per task under `<parent>/<repo>-worktrees/<branch>`, never the main checkout. Copy untracked local config the code needs (e.g. `.env`) from the main checkout.
- Packages inside the workspace: worktree the workspace repo itself (`<parent>/<workspace>-worktrees/<branch>`). Context files are still edited only in the main checkout.

## TDD: coder + unit-test-writer
- The main session is team lead. It writes one spec and sends the same spec to both: scope, interface (module paths, signatures, behaviour) and acceptance scenarios.
- Two subagents run in parallel and never communicate.
- The unit-test-writer gets its own worktree at the same base commit. It sees existing code and fixtures, never the coder's diff. Its tests must first fail for the right reason.
- Each agent uses its own test state (temp dirs, databases, ports). The exact test command per package or repo is in `AGENTS.md` "Code". Confirm the "N passed" line: warnings print after it.
- The lead merges the tests into the task worktree and runs them. Each failure is classified against the spec:
  - Code bug: back to the coder.
  - Test bug: back to the test-writer with behaviour-level notes only, never implementation.
  - Spec gap: the lead amends the spec and sends it to both.
- After 3 rounds on the same failure, stop and ask the human.
- For exploratory or throwaway code (a spike, a one-off analysis), the lead may write code and tests itself; say so.

## Docstrings and comments (both agents)
- Scope: touched functions and methods, their enclosing class, and the module of any touched file. Test files included (one-line docstrings). Leave untouched code alone.
- Those docstrings must exist, trimmed and simple.
- Move inline comments in touched symbols into the docstring. Keep one only if absolutely necessary.

## Finishing
- Check `git branch --show-current` first. Commit on the task branch, no AI attribution.
- With a remote: push the task branch. Never force-push, and never push main unless asked.
- Merge into main only when the human asks; otherwise leave the branch for them. Nothing else goes outward except the steps below; the other hard rules in `AGENTS.md` still apply.

## Optional: PRs (only for repos marked `PRs: yes` in `AGENTS.md` "Code")
- After pushing, open a ready PR (not draft) with no reviewers, following the repo's PR template if it has one. The human merges it.
- Review-bot comments on the session's PR, if a bot reviews it: assess each, fix the ones worth fixing through the TDD loop, push, then resolve the bot's threads. No replies; human reviewers' threads are left alone.

## After merge
- Only if `AGENTS.md` "Issue tracker" lists them: perform the post-merge tracker steps on the task's ticket. Read back each change; report anything that failed or didn't apply.

## Optional: shared-stack QA
Only for projects that declare a QA stack in `AGENTS.md` "Code": a long-running local service, database or device that parallel sessions would otherwise trample. Everything else stops at step E.
- One lock per stack: `scripts/qa-lock.sh`. The lead waits, never an agent: run `scripts/qa-lock.sh acquire <stack> <task> <worktree>` as a background shell; the token is the first line of its output.
- Once the lock is held, a QA subagent gets the token, worktree and scenarios, and owns the lock:
  1. `scripts/qa-<stack>-stack.sh prepare <token> <worktree>`: fresh state from a clean baseline, serve the worktree.
  2. Run the scenarios; report evidence per scenario.
  3. `scripts/qa-lock.sh check <stack> <token>` before reporting: a failed check means the lock was taken over and the results are void.
  4. `scripts/qa-<stack>-stack.sh restore <token>`, then `scripts/qa-lock.sh release <stack> <token>`.
- If the agent returns with the lock still held, the lead restores and releases. Never change a shared stack without holding its lock.
- A lock is stale once its session is gone or it passes 2 hours; the next waiter takes it over (`scripts/qa-lock.sh status <stack>`).
- On failure: restore and release first, fix through the TDD loop, re-queue. After 3 failed cycles, stop and ask the human.
- No stack script yet: write one from `scripts/qa-stack.example.sh`.
