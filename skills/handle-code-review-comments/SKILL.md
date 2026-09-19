---
name: handle-code-review-comments
description: Walk through unresolved human code review comments on the current branch's PR, propose a fix for each, ask the user how to proceed, and optionally reply to the reviewer. Use when the user asks to handle, address, respond to, or work through PR review comments, or mentions "/handle-code-review-comments".
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, AskUserQuestion
---

# Handle Code Review Comments

Walk the user through every unresolved human review comment on the current branch's pull request, one at a time: propose a fix, show it, ask how to proceed, then optionally reply to the reviewer.

## Workflow

### 1. Locate the PR for the current branch

```bash
# If GITHUB_TOKEN is set in the environment but lacks repo access,
# unset it for this command so gh falls back to the keyring token.
gh auth status 2>&1 | grep -q "GITHUB_TOKEN" && UNSET_TOKEN="GITHUB_TOKEN= " || UNSET_TOKEN=""
eval "${UNSET_TOKEN}gh pr view --json number,url,headRefName,baseRefName,state"
```

If the command fails with "no pull requests found", stop and tell the user there is no PR for this branch. Do not create one.

Capture: `OWNER`, `REPO`, `PR_NUMBER`. Derive owner/repo from `gh repo view --json owner,name`.

### 2. Fetch unresolved human review threads

Use the GraphQL API, REST does not expose `isResolved` for review threads.

```bash
eval "${UNSET_TOKEN}gh api graphql -F owner='$OWNER' -F name='$REPO' -F number=$PR_NUMBER -f query='
query(\$owner: String!, \$name: String!, \$number: Int!) {
  repository(owner: \$owner, name: \$name) {
    pullRequest(number: \$number) {
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          comments(first: 50) {
            nodes {
              id
              databaseId
              author { login __typename }
              body
              path
              line
              originalLine
              startLine
              diffHunk
              url
              createdAt
            }
          }
        }
      }
    }
  }
}'"
```

Filter the returned threads:

- Drop threads where `isResolved == true`.
- Drop threads where the **first** comment's author has `__typename == "Bot"` or `login` ends with `[bot]` (e.g. `coderabbitai[bot]`, `sonarcloud[bot]`, `github-actions[bot]`).
- Keep `isOutdated` threads but flag them, the line numbers may not match current HEAD.

If zero threads remain, tell the user "No unresolved human review comments." and stop.

### 3. Build the work queue

For each remaining thread, extract:

- `thread_id` (GraphQL node ID, needed to resolve later)
- `first_comment_id` (REST `databaseId` of the first comment, needed to reply)
- `author`, `path`, `line`, `body`, `diffHunk`, `url`
- All follow-up comments in the thread (for context, the reviewer may have clarified)

Order the queue by `path` then `line` so related comments cluster together.

### 4. Loop through comments one at a time

For each thread in the queue:

#### 4a. Present the comment

Show the user, in this exact shape:

```
Comment N of M  •  @<author>  •  <path>:<line>
<url>

> <comment body, blockquoted, preserving line breaks>

[follow-ups, if any, indented and labeled with author]
```

#### 4b. Read the surrounding code

Read the file at `path`. Read at least 30 lines of context around `line`. If the thread is `isOutdated`, search for the original code in the diff hunk to locate the current equivalent, say "thread is outdated, line numbers shifted" if you cannot find an exact match.

#### 4c. Propose a fix

Decide what the reviewer is asking for. If the comment is:

- **A concrete change request** ("rename X to Y", "extract this", "use Z instead"), propose the exact edit.
- **A question** ("why are we doing X?"), propose a reply that answers it; no code change unless the answer reveals a bug.
- **A nit / style preference**, propose the smallest possible edit.
- **Ambiguous**, say so explicitly. Propose your best interpretation but flag the ambiguity in the question to the user.
- **Already addressed** in the current code (common with outdated threads), say so; propose only a reply.

Show the proposed fix as a unified diff (file path + before/after hunks). For reply-only proposals, show the draft reply text in a fenced block.

#### 4d. Ask how to proceed

Use `AskUserQuestion` with these options (omit options that don't apply):

- **Apply**, write the edit to disk.
- **Apply + reply**, write the edit and post a reply to the reviewer.
- **Reply only**, post the reply without editing code.
- **Skip**, leave this comment for later, move to next.
- **Stop**, exit the loop entirely.

If the user picks an "Apply" option, make the edit with the `Edit` tool, then re-read the file to confirm. Do not stage or commit, that's a separate workflow.

#### 4e. Optionally reply to the reviewer

If the user chose any "reply" option:

1. Draft the reply (1–3 sentences). Default tone: direct, no filler ("Done." / "Good catch, fixed in <short description>." / "Intentional because <reason>.").
2. Show the draft and confirm with `AskUserQuestion`: **Send** / **Edit** / **Skip reply**.
3. On Send, post via REST:

```bash
eval "${UNSET_TOKEN}gh api -X POST repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments/$FIRST_COMMENT_ID/replies -f body=\"\$REPLY_BODY\""
```

Do **not** automatically resolve the thread, the reviewer resolves it after they're satisfied.

### 5. Wrap up

After the loop ends (user chose Stop, or queue exhausted), report:

- Comments addressed (with file:line for each)
- Comments skipped
- Comments replied to
- Files modified (so the user knows what's pending commit)

Do not commit, push, or mark threads resolved unless the user explicitly asked.

## Filtering rules, humans vs bots

A comment is from a **bot** if any of:

- GraphQL `author.__typename == "Bot"`
- `author.login` matches `*[bot]` (case-insensitive)
- Known reviewer bots: `coderabbitai`, `sonarcloud`, `sonarqubecloud`, `codecov`, `github-actions`, `dependabot`, `renovate`

When in doubt (e.g. a service account with a human-looking name), include it and let the user skip if unwanted.

## Anti-patterns to avoid

- Don't fetch all PR comments via `gh pr view --json comments`, that returns issue comments (general PR discussion), not line-level review comments.
- Don't use `/repos/{owner}/{repo}/pulls/{n}/comments` REST endpoint for the queue, it has no `isResolved` field. Use GraphQL `reviewThreads`.
- Don't batch-apply fixes across multiple comments without confirming each one individually, the user wants per-comment control.
- Don't auto-resolve threads. Resolution is the reviewer's signal that the conversation is done.
- Don't commit or push as part of this workflow. Hand off to the commit workflow when the user is ready.
- Don't reply with templated fluff ("Thanks for the feedback!"). Keep replies short and substantive.
- Don't skip the `GITHUB_TOKEN=` unset dance if `gh auth status` shows the active account is `GITHUB_TOKEN`, many private repos require the keyring token instead.
- Don't use em dashes (, ) in your replies to code review comments
