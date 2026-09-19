---
name: cleanup-context
description: Aggressively prune the folder's context files down to current state, delete closed/finished items, compress history, fix dangling references. Use when the user types "/cleanup-context" or asks to clean up, prune, or slim down the context files.
---

# Cleanup context

Ingest the main context files first if you haven't already, then prune them aggressively so they carry only what's current, without hurting the overall integrity of the context. Use your judgement throughout; the principles below matter more than any fixed procedure:

- **Delete closed/finished steps; keep everything open or unfinished intact.** The one exception: history worth keeping survives as a heavily compressed timeline (roughly one line per date/milestone), not as narrative.
- **Promote before deleting.** If a closed item contains a durable fact, ruling, or mechanic not yet recorded in the durable reference file, move it there first.
- **Don't break references.** Preserve section numbering/anchors that other files cite, and repoint or annotate anything that would dangle (including references to files that were deleted).
- **Lean on git history** (when the folder is a repo): note in the file that pruned detail is recoverable from git history rather than trying to preserve it inline.
- **Respect the file's charter.** A volatile state file should read like "what's happening now"; a durable reference file should barely change. Leave archives (outbox-style dated folders, sent records) untouched, a dangling mention inside an archive is provenance, not a defect.

When done, report what was pruned, what was promoted, and any references you patched.
