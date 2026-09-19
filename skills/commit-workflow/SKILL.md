---
name: commit-workflow
description: 'Execute git commit with conventional commit message analysis, intelligent staging, and message generation. Use when user asks to commit changes, create a git commit, or mentions "/commit". Supports: (1) Auto-detecting type and scope from changes, (2) Generating conventional commit messages from diff, (3) Interactive commit with optional type/scope/description overrides, (4) Intelligent file staging for logical grouping'
allowed-tools: Bash
---

# Commit Workflow (Conventional Commits)

## Format

```bash
<type>(<optional scope>): <description>

WHY: <1–3 lines/bullets explaining why>

[BREAKING CHANGE: ...] -- optional, if applicable
[other footers]
```

- First line always: `<type>(<scope>): <description>`
- Description: imperative, present tense, <72 chars
- WHY goes in body (not title). Explain motivation, not diff.

## Ticket Code

```bash
git branch --show-current | grep -o '^\w*\_[1-9][0-9]*' | tr \_a-z -A-Z
```

Footer order:

1. `BREAKING CHANGE: ...` (if applicable)
2. Any other optional footers (`Refs #...`, `Closes #...`, etc.)

## Commit Types

| Type       | Purpose                        |
| ---------- | ------------------------------ |
| `feat`     | New feature                    |
| `fix`      | Bug fix                        |
| `docs`     | Documentation only             |
| `style`    | Formatting/style (no logic)    |
| `refactor` | Code refactor (no feature/fix) |
| `perf`     | Performance improvement        |
| `test`     | Add/update tests               |
| `build`    | Build system/dependencies      |
| `ci`       | CI/config changes              |
| `chore`    | Maintenance/misc               |
| `revert`   | Revert commit                  |

## Rules

- Small commits. One scope + one intent per commit.
- Split multi-scope changes (`git add -p`).
- No drive-by edits. Separate style/refactor.
- WHY required in every commit (unless trivial rename/format).

## Workflow

### 1. Inspect

```bash
# If files are staged, use staged diff
git diff --staged

# If nothing staged, use working tree diff
git diff

# Also check status
git status --porcelain
```

### 2. Stage intentionally (if needed)

If nothing is staged or you want to group changes differently:

```bash
git add -p
git add <file>
```

### 3. Commit

```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <description>

WHY: <reason>

BREAKING CHANGE: <if any>
EOF
)"
```

## Examples

```
feat(search): add VIN filter to query builder

WHY: Users need to narrow results by VIN to reduce false positives in imports.
```

```
refactor(api): centralize error mapping

WHY: Reduce duplicated error handling and ensure consistent client messages.
```

```
docs(readme): clarify local setup steps

WHY: New joiners were missing required env vars and failing setup.
```

## Safety

- NEVER modify git config
- NEVER run destructive commands (--force, hard reset) without explicit request
- NEVER skip hooks (--no-verify) unless user asks
- NEVER force push to main/master
- NEVER commit secrets (.env, credentials.json, private keys).
- If commit fails due to hooks, fix and create new commit (don't amend)
