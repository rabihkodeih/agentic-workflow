---
name: generate-test-cases
description: Generate a comprehensive set of manual test cases from the diff between the current branch and master. Use when the user asks to generate, write, or produce test cases for a branch, reviews a PR and needs test coverage, or mentions "/generate-test-cases". Produces a markdown file using the project's table format (TC-N numbering with Precondition / Steps / Expected / Notes fields).
allowed-tools: Bash, Read, Grep, Glob, Write
---

# Generate Test Cases from Branch Diff

Analyze the diff between the current branch and `master`, then produce manual test cases covering every user-observable behavior the branch introduces or changes.

## Workflow

### 1. Collect the diff

```bash
git fetch origin master --quiet 2>/dev/null || true
BASE=$(git merge-base HEAD origin/master 2>/dev/null || git merge-base HEAD master)
git diff "$BASE"...HEAD --stat
git diff "$BASE"...HEAD
```

Use `git merge-base` (three-dot `...`), never a plain two-dot range, prevents noise from master advancing.

### 2. Understand the change, not just the diff

- Read every file the diff touches (not only the changed hunks). Context outside the hunk often determines the expected behavior.
- Read new files in full.
- Identify user-facing surfaces: routes, pages, components, forms, auth flows, redirects, data fetching, validation, conditional rendering, responsive behavior, localization, feature flags, error states.
- Skip: pure refactors, type-only edits, dependency bumps, tooling config without runtime impact, test-only changes.

### 3. Classify coverage dimensions

For each user-facing behavior, think through these dimensions and emit a case for each that applies:

- **Happy path**, the main successful flow
- **Preconditions**, fresh session, authenticated user, specific data state
- **URL variants**, root, with query params, with hash, deep links
- **State persistence**, reload, new tab, browser close, across navigation
- **Error / empty states**, invalid input, failed request, empty list
- **Access control**, unauthenticated redirect, role gating
- **Responsive**, mobile (~375px) and desktop (~1280px) breakpoints
- **Cross-cutting**, logout, session expiry, cookie/storage behavior, i18n

Skip dimensions that don't apply. Don't pad.

### 4. Emit test cases in the required format

Write to `<branch-name>-test-cases.md` at repo root unless the user specifies a different path. One markdown table per test case, exactly like this:

```markdown
### TC-N: <Short, specific title>

| Field            | Value                                                           |
| ---------------- | --------------------------------------------------------------- |
| **Precondition** | <Starting state>                                                |
| **Steps**        | 1. <First action>                                               |
|                  | 2. <Second action>                                              |
| **Expected**     | <Observable outcome, URL, visible text, element style, cookie> |
|                  | <Additional expected outcome on its own row>                    |
| **Notes**        | <Optional, cite code or edge case when non-obvious>            |
```

Rules:

- Number consecutively from TC-1.
- Title ≤ 60 chars, states WHAT is verified (not HOW).
- Precondition describes the starting state, not setup steps.
- Each step is a single imperative action a human tester performs.
- Expected is observable: specific URLs, exact visible text, element position/style, cookie values. Never reference internal state (Redux, React context, hooks).
- Multi-line Steps / Expected use continuation rows with an empty first cell (`|  |`), matching the project's existing test-case files if it has any.
- Omit the Notes row when there's nothing useful to say, don't leave an empty cell.

### 5. Coverage checklist

Before finalizing, confirm the file covers:

- [ ] Every new route / page (and unauthenticated access if auth-gated)
- [ ] Every new form (submit success + validation failure)
- [ ] Every new interactive element whose state/UI changes on interaction
- [ ] Auth & session flows, if auth was touched, login, logout, refresh, new tab, browser close
- [ ] URL preservation (query params + hash), if redirects were touched
- [ ] Responsive behavior for any new UI, mobile and desktop
- [ ] Integration points the diff could plausibly break

### 6. Report back in chat

After writing the file, respond with:

- File path
- Number of test cases
- Dimensions covered (e.g., "routing, auth, URL preservation, responsive")
- Dimensions deliberately skipped and why (e.g., "no forms touched, skipped validation cases")

## Anti-patterns to avoid

- Don't generate cases for unreachable code (pure utilities, type helpers).
- Don't invent behaviors the diff doesn't introduce.
- Don't write cases whose Expected is invisible to a tester.
- Don't number cases by file; number by logical user flow.
- Don't duplicate cases that differ only in trivial phrasing, consolidate.
