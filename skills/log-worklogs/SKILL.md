---
name: log-worklogs
description: 'Log Tempo timesheet entries to Jira worklogs from a freeform bullet list. Use when the user asks to log Tempo hours, post worklogs, add time to Jira, log time for yesterday/today/<date>, update their daily timesheet, or pastes a list of `> TICKET-KEY :: Nh` blocks. Also trigger on phrases like "log my tempo hours", "post my hours", "add worklog for <TICKET>", "log time for <date>".'
allowed-tools: mcp__plugin_atlassian_atlassian__addWorklogToJiraIssue, mcp__plugin_atlassian_atlassian__getJiraIssue, Bash
---

# Log worklogs

Parse a freeform list of ticket entries with hours and bullets, then post each one as a Jira worklog via the Atlassian MCP plugin. Tempo reads Jira worklogs directly, so they appear in the Tempo timesheet automatically , **never use a browser or the Tempo UI** (the Connect iframe makes it painfully slow).

## Input format

The user pastes blocks like:

```
> TICKET-KEY :: <duration>
    (optional header line, e.g. "Catch-up / Planning")
    - bullet 1
    - bullet 2
        - nested sub-bullet
        - another sub-bullet

> ANOTHER-KEY :: <duration>
    - bullet
```

- Duration accepts Jira time format: `Nh`, `Nm`, `N.Nh`, `Nh Nm`, `0.5h`, etc.
- Description = every indented line after the `> ... ::` line, up to the next `>` or blank line.
- Copy description text **verbatim**. Do not reword, summarize, or strip leading `(...)` headers. Bullets stay bullets.
- **Preserve bullet nesting.** Bullets indented deeper than their siblings are sub-bullets , keep their relative indentation so they render as nested sublists, not flattened to a single level.

## Date resolution

The user may say "yesterday", "today", "Monday", "May 13", or give an explicit date.

- Resolve relative dates against the timezone in **User context** below.
- Default to **today** if unspecified.
- If ambiguous (e.g., "Monday" with no week context), ask which week before posting.

## Steps

1. **Parse all entries first.** If any block fails to parse, stop and ask the user to clarify before posting *anything* , no partial logging.
2. **Sanity-check totals.** Sum the durations. If the total exceeds **8h**, surface the breakdown and ask the user to confirm. Could be intentional (overtime) or a typo (e.g., `5h` instead of `0.5h`).
3. **Validate unknown ticket keys.** For any ticket key that is not in the shorthand list below, call `getJiraIssue` to confirm it exists. If it 404s, stop and ask.
4. **Duplicate guard (best-effort).** If the user explicitly mentions a past date *and* the bullets look identical to recent ones for the same ticket, flag it before posting. Otherwise proceed , duplicate detection across the full Jira worklog history isn't worth the API cost for the common case.
5. **Post worklogs in parallel.** In a single message, dispatch all `addWorklogToJiraIssue` calls at once. For each entry:
   - `cloudId`: the Atlassian site from **User context**
   - `issueIdOrKey`: the ticket key
   - `timeSpent`: the parsed duration string (e.g., `1h`, `2h30m`, `0.5h`)
   - `started`: ISO 8601 with the target date and staggered hours (09:00, 10:00, 11:00, ... UTC) so multiple entries on the same day don't overlap each other on the Tempo timeline
   - `commentBody`: the description **verbatim** , keep the `(...)` header line if present, keep the bullet markers (`- `) intact, and **preserve the indentation of nested bullets**. Normalize each nesting level to 4 spaces of indentation relative to its parent (strip any trailing whitespace on lines, but never collapse leading indentation that signals nesting).
   - `contentFormat`: `"markdown"` , Jira auto-converts `- ` prefixes into a proper bulletList in ADF, and indented `- ` lines into nested `bulletList`s within their parent `listItem`
6. **Print a summary table.** After all calls complete:

   ```
   | Ticket | Hours | Worklog ID |
   |---|---|---|
   | ... | ... | ... |
   | **Total** | **Nh** | |
   ```

   Then tell the user to refresh the Tempo timesheet to see the entries.

7. **Failure handling.** If any worklog call fails, report which entries succeeded and which failed with the error message. **Do not retry blindly** , ask how to proceed.

## User context (defaults, fill in per person)

- Atlassian site: `<yourorg>.atlassian.net`
- Timezone: `<IANA zone the timesheet is kept in, e.g. America/Toronto>`
- Common shorthand keys (skip validation for these):
  - `TIME-1` → General meetings (not project specific)
  - `TIME-2` → General non-project work
  - `PROJ-*` → main product project

## Do NOT

- Use a browser or the Tempo UI. Tempo reads Jira worklogs, so the API is the right path and is ~50× faster.
- Reword, summarize, or "clean up" bullet text. Copy verbatim, including grammar quirks.
- Flatten nested bullets to a single level. Preserve the indentation hierarchy so sub-bullets stay nested under their parent.
- Post anything if the parse is incomplete or the daily total looks wrong , ask first.
- Retry on partial failure , surface what happened, let the user decide.
- Assume timezone , if the user is in a different TZ for a trip, ask before resolving "yesterday/today".

## Example invocation

User:
> Please log my tempo hours for yesterday:
> ```
> > TIME-2 :: 1h
>     (Catch-up / Planning)
>     - reviewed slack
>     - groomed TODOs
> > PROJ-1234 :: 3h
>     - investigated s3 output option
>     - finalized design doc
> ```

Expected behavior:
1. Resolve "yesterday" → ISO date in the configured timezone.
2. Parse 2 entries totaling 4h (under 8h, no confirmation needed).
3. Skip ticket validation (`TIME-2` and `PROJ-*` are known shorthand).
4. Dispatch 2 `addWorklogToJiraIssue` calls in parallel with staggered `started` times.
5. Print summary table; remind user to refresh Tempo.
