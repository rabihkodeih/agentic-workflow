---
name: pr-workflow
description: Use this skill when asked to create or update a pull request (PR). It ensures all PRs
  follow the repository's established templates and standards. Handles both new PR creation and updating
  existing PRs with new commits, title changes, or description updates.
---

# PR Workflow

This skill guides the creation and maintenance of high-quality Pull Requests that adhere to the repository's standards. Use it to create new PRs or update existing ones with new commits, title changes, or description updates.

## CRITICAL: Tool Requirements

**ALWAYS use `gh` (GitHub CLI) for ALL GitHub operations.**

- Use `gh pr create`, `gh pr edit`, `gh pr list`, `gh pr view`
- Use `gh api` for custom GitHub API calls
- NEVER use `git` commands for GitHub-specific operations (creating PRs, managing PRs)

The `gh` CLI is the official GitHub tool and provides the best integration, error handling, and user experience.

## Workflow

Follow these steps to create a Pull Request:

### 1. Branch Management

**CRITICAL:** Do NOT work on `master`.

```bash
git branch --show-current
```

If current branch is `master`, create and switch:

```bash
git checkout -b <new-branch-name>
```

### 2. Commit Changes

Ensure all changes are committed.

```bash
git status
```

If there are uncommitted changes:

- Use the `commit-workflow` skill.
- Ensure proper conventional commit format with `WHY` in the message.

### 3. Locate and Read PR Template

Search for:

- `.github/pull_request_template.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/PULL_REQUEST_TEMPLATE/`

If multiple templates exist, select the most appropriate one (or ask the user).

Read the template content.

### 4. Draft PR Description

Strictly follow the template structure.

- **Headings**: Keep all headings.
- **Checklists**: Review each item. Mark with `[x]` if completed. If an item
  is not applicable, leave it unchecked or mark as `[ ]` (depending on the
  template's instructions) or remove it if the template allows flexibility
  (but prefer keeping it unchecked for transparency).
- **Content**: Fill in the sections with clear, concise summaries of your
  changes. Remove the sections that are not relevant instead of leaving them
  blank, unless the template specifies otherwise.
- **Related Issues**: Link any issues fixed or related to this PR (e.g.,
  `Fixes #123`).
- **JIRA Tickets**: When available, include full links in the form
  `https://<yourorg>.atlassian.net/browse/<ticket code>`.

### 5. Push Branch

**CRITICAL**: Verify branch is NOT master.

Push the current branch to the remote repository.

```bash
git branch --show-current
git push -u origin HEAD
```

### 6. Create or Update PR

First, check if a PR already exists for the current branch:

```bash
gh pr list --head "$(git branch --show-current)" --state open
```

- If an open PR exists for this branch, update it (push commits + edit title/body if needed).
- If no PR exists, create a new one.

#### 6a. Title Rules

If a Jira ticket exists, the PR title MUST be: `<TICKET-CODE>: <short summary>`
Example: `PROJ-225: add FetchButton with multi-provider support`

Ticket code rules:

- Must match `^[A-Z]+-\d+$` (uppercase project key, hyphen, number).
- If the branch contains a ticket in lowercase (e.g. `proj-44`), use `PROJ-44` in the PR title.

Short summary rules:

- 3–8 words (aim for ~50 chars max).
- Start with an imperative verb: Add, Fix, Update, Refactor, Remove, Document.
- Describe the net change, not the process.
- Do not include extra metadata like `docs(...)`, branch name, “analysis”, “plan”, etc.
- Do not list multiple items separated by commas - pick the primary outcome.

If no ticket exists, fall back to Conventional Commits: `<type>(<scope>): <short summary>`
Example: `docs(menu): Add specs and rollout notes`

#### 6b. How to get a good title

1. Get the ticket code from the branch name:

```bash
git branch --show-current
```

2. Review all commits on the branch relative to the base branch and write a short title for the combined intent:

```bash
git log --oneline --no-merges origin/master..HEAD
```

#### 6c. Creating a New PR

Write description to a temporary file, then:

```bash
gh pr create \
  --title "<TICKET-CODE>: <short summary>" \
  --body-file <temp_file_path>
```

#### 6d. Updating an Existing PR

Identify the PR number (from gh pr list or gh pr view) and run:

```bash
gh pr edit <pr-number> \
  --title "<TICKET-CODE>: <short summary>" \
  --body-file <temp_file_path>
```

Afterwards, remove the temporary file:

```bash
rm <temp_file_path>
```

## Principles

- **Compliance**: Never ignore the PR template. It exists for a reason.
- **Completeness**: Fill out all relevant sections.
- **Accuracy**: Don't check boxes for tasks you haven't done.
- **Idempotence**: Prefer updating an existing PR for the same branch over creating a new one.
