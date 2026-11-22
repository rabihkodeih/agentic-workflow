# context-repo-template

A self-contained workspace for one project. Start a new one with:

```
scripts/clone-ws.sh <path-to>/context-repo-template ~/projects/<name>
```

That copies the template, fills the `mother-context.md` stub, and makes the first commit. A plain `cp -R` works too; then fill the `<project>` placeholders by hand. Next: edit `AGENTS.md` ("Code", "Issue tracker"), seed `mother-context.md`, and start a session with `/ingest-context`.

- `AGENTS.md`: rules, layout, code map, optional issue tracker. Edit once, then rarely.
- `CLAUDE.md`: imports `AGENTS.md` and `dev-workflow.md` so every session loads both.
- `dev-workflow.md`: how code changes are made: task pipeline, worktrees, TDD, finishing, the only outward actions allowed, and an optional shared-stack QA appendix.
- `mother-context.md`: current state. Revised every session, in place.
- `domain-knowledge.md`: how the domain works, with sources. Changes rarely.
- `human-notes.txt`: human-only. The agent reads it and never writes it.
- `outbox/`: drafts for humans, not yet sent.
- `plans/`: one plan file per task, deleted once merged.
- `scripts/`: small helpers (workspace cloner, CI babysitter, and the optional QA lock and stack skeleton).
- `packages/`: packages and libraries built inside the workspace. Code can also live in sibling repos next to it; see `AGENTS.md` "Code".
- `.clone/`, `.cloneignore`: what `clone-ws.sh` stubs and skips, so a workspace can spawn per-task clones of itself.
- `.claude/settings.json`: baseline permissions (read-only git/gh allowed, destructive git denied).
