# <project> workspace: agent rules

Rules for any agent working in this workspace. What the workspace is for is stated at the top of `mother-context.md`. Keep this file lean: it routes and states behaviour, it is not the library.

## Hard rules
- Do not edit `human-notes.txt`. Human input only.
- Never send, post, reply, comment, transition or log work on the human's behalf (chat, email, issue tracker, docs, code host). Drafts go to `outbox/`; the human sends them. Only exceptions: the push, optional PR and post-merge steps in `dev-workflow.md`.
- Production is read-only. Any prod change is typed by a person.
- Commits and PRs: no AI-attribution line; the human is the sole author. Never push unless asked or allowed by `dev-workflow.md`.
- Never write a credential, token or secret into any file, draft or tool output. Print variable names only.
- Verified vs inferred, always. Tag every claim with its source or flag it as inferred. Don't manufacture findings.

## Models
- Reasoning and research: the most capable model. Spend its tokens where deduction matters.
- Bulk or simpler work (sweeps, test writing, first-pass reviews) goes to subagents on a cheaper model, never the top one.

## Knowledge map (read both before substantive work)
- `mother-context.md`: volatile state. Situation, plan, tasks and their branches, decisions in flight, open questions, milestone log. Revise in place after anything that changes the picture; don't append.
- `domain-knowledge.md`: durable mechanics and provenance, each claim source-tagged and confidence-flagged. Update only when a mechanic or its source changes.
- Boundary rule: settled fact about how the world works → `domain-knowledge.md`; current state of the work or an open question → `mother-context.md`. On conflict, `domain-knowledge.md` wins on mechanics, `mother-context.md` on "what's happening now".

## Layout
| Path | Holds |
|---|---|
| `AGENTS.md` | these rules; edit once, then rarely |
| `dev-workflow.md` | how code changes are made: task pipeline, worktrees, TDD, finishing, optional QA |
| `mother-context.md` | current state |
| `domain-knowledge.md` | how the domain works, with sources |
| `human-notes.txt` | human-only notes; read, never write |
| `outbox/` | drafts for humans, not yet sent |
| `plans/` | one plan file per task, deleted once merged |
| `scripts/` | small single-purpose helpers (workspace cloner, CI babysitter, optional QA lock) |
| `packages/` | software packages and libraries developed inside this workspace |
| `archive/` | things moved aside instead of deleted (created on first use) |

## Code
Code lives in one of two places. List every package and repo in the table.
- **In the workspace:** `packages/<name>/`, self-contained (own manifest, tests, README). See `packages/README.md`.
- **Outside:** a sibling repo, `<parent>/<repo>`, worktrees under `<parent>/<repo>-worktrees/<branch>`. Use this when the code is shared with a team or outgrows the workspace.

| Name | Where | Kind | Tests | Notes |
|---|---|---|---|---|
| | | | | |

Optional flags in Notes: `PRs: yes` if the repo works through pull requests (default: plain branches merged into main); `direct-to-main: yes` if small changes may skip the side branch; `QA stack: <name>` only for a long-running service or database that parallel sessions share; see `dev-workflow.md` "Optional: shared-stack QA".

## Workspaces
- One project, one root workspace. When work runs in parallel, spin off a workspace per task or initiative: `scripts/clone-ws.sh . ../w-<name>`. Small projects can stay in one.
- Task state stays in its own workspace. The root's `domain-knowledge.md` and `dev-workflow.md` are authoritative; a clone's copies are snapshots. Promote durable findings back as an explicit, reported edit.

## Issue tracker (optional)
- Default: none. Tasks are named by a short slug (`fix-login-timeout`) and tracked in `mother-context.md`.
- If the project uses one, state it here: tool, project key, board, and which post-merge steps the agent may perform (fields, transitions). Task id = the issue key, lower-cased for branches (`proj_123`). The agent touches only tickets of its own task.

## Domain rules
- Never `rm` / `rm -rf`. Move things to `archive/` or the session scratchpad, or leave deletions to the human.
- Write commands the permission classifier blocks: prepare the exact command; the human approves it or runs it with `!`.
- Before any destructive infra command (registry/image deletes, instance termination, resource destroy), prove each target unused from IaC and CI references, not from last-used timestamps. Present evidence per item; when unsure, leave it out.
- Customer or personal data: committed files carry aggregates and IDs only; raw payloads stay in the session scratchpad.
- Name the repo or package in every claim about code.
- Check `git branch --show-current` before committing in any repo; something outside the session may have switched branches.
- Local runs never hit a real third party: point integrations at test endpoints and keep scheduled jobs off.
- A credential seen in chat or email is compromised: reference it by name, flag rotation to the human. Never rotate a working credential on a hunch.
- Scripts that write to production or prod-adjacent systems run as a dry-run first.
- Never claim a check passed without running it or having CI evidence; list skipped checks.

## Development
`dev-workflow.md` holds the default task pipeline and the only outward actions the agent may take on its own. It is loaded through `CLAUDE.md`. Any stricter rule in this file wins.

## Sources
- Search every available source before concluding: code, issue tracker, docs, chat, code host, read-only databases. Say which were used and which weren't.
