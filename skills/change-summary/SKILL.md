---
name: change-summary
description: Generate a change-advisory (CAB) summary for the current branch (or a branch the user names) and post it to the Jira ticket. Use when the user types "/change-summary", asks for "CAB info", "change summary", or "change advisory board info" for a branch, PR, or ticket.
---

# Change summary

Produce a change-advisory (CAB) section for a branch's changes using the template below, then post it to the ticket. Adjust the field list to whatever your release board expects; keep the labels verbatim once set.

## Inputs

- **Branch**: the branch named by the user, else the repo's current branch. Diff it against its base (the branch the PR targets; else `develop` if it exists, else the default branch) using the merge base, `git diff $(git merge-base <base> <branch>)...<branch>`.
- **Jira ticket**: use the URL or key the user provided. If none was provided, try to infer it from the branch name (e.g. `proj_1234` → PROJ-1234) or from commit message prefixes, then **ask the user to confirm** (AskUserQuestion, offering the inferred candidate). If nothing is inferable, ask the user for the ticket URL, never guess-post.

## Gather facts before writing

1. **The change itself**: changed files + PR title/description if a PR exists (`gh pr view`). Understand what it does and why, enough to explain it to a technically skilled reader who doesn't know the repo.
2. **Config/flag gating**: check the diff for feature flags, settings/config entries, DB-backed configuration (e.g. route/config models, admin-managed toggles). Only mention gating in the output if it actually exists.
3. **Coverage**: get the % from SonarQube (MCP: `get_project_quality_gate_status` / `get_component_measures` for the PR or branch) or from CI output. If neither yields a number, use "Not Available". Do not estimate.
4. **DB changes**: look for migration files / schema changes in the diff. If present, assess downtime safety knowing DB changes deploy **before** the code (e.g. additive enum/column changes are safe; drops/renames are not).
5. **Affected services**: derive from the touched paths (apps, services, handlers), a short list, not a file dump.

## Template (fill exactly this structure)

```
**Description**: Briefly and clearly describe what the PR changes, including the context and rationale. Target technically skilled readers who are unfamiliar with the repo. No need to go into too much details about the code changes as it is meant for reviewers who do not necessarily know the code thoroughly. Do mention if changes are controlled via configs or feature flags. If not do not mention it.
Try to keep it short and to the point, but include enough detail to understand the changes.
**Risk**: Assess the risk of the changes as low, medium, or high. Mark as low if downtime safe, not critical, and not end-user impacting.
**Risk Summary**: Explain your risk assessment. If changes are controlled by DB config or feature flag, mention it.
**Coverage**: Report the % code coverage from SonarQube or CI, or say "Not Available" if not found.
**DB Changes**: List any DB changes (migrations, schema, etc.) or say "NA". If present, assess downtime safety given the deployment process (DB changes precede code deploy).
**Revert Strategy**: Briefly state how to revert if needed; usually, "Rollback the code deployment". If not applicable, say "NA".
**Affected Services**: Provide a short list of affected services.
```

Rules:

- Keep every field label verbatim (`**Description**:` … `**Affected Services**:`), in this order, nothing added or dropped.
- Replace each field's instructional text with the actual content; never leave template prose in the output.
- Short and factual. No hedging, no code walkthroughs.
- Risk defaults: downtime-safe + not critical + not end-user-impacting → low. Escalate to medium/high only with a concrete reason (schema risk, live-traffic behavior change, irreversible data effects) and say why in Risk Summary.

## Post to Jira

Post the CAB Information section at the **bottom of the ticket's Description**, not as a comment.

1. Show the filled section to the user in the reply.
2. Fetch the current Description (`getJiraIssue`), then update it via the Atlassian MCP (`editJiraIssue`):
   - If the Description already contains a CAB Information section (a "CAB Information" heading or a `**Description**:`…`**Affected Services**:` block), **replace** that existing section in place, do not append a duplicate.
   - Otherwise, **append** the section to the end of the existing Description, preserving everything already there. Separate it from the prior content with a blank line (and a `CAB Information` heading).
   - Never overwrite or drop the rest of the Description.
3. Convert formatting for Jira if needed (the `**bold**` labels must render bold in Jira).
4. Report the updated ticket link back to the user. If the update fails, show the section and the error so the user can paste it manually.
