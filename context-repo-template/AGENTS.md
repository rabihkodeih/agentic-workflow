# <project> context repo

Rules of engagement for any agent working here. Keep this file lean: it routes to the knowledge files and states behaviour, it is not itself the library.

## Hard rules
- Do not edit `human-notes.txt`. Human input only.
- Never send, post, reply, comment or commit on the human's behalf. Drafts go to `outbox/`; the human sends them.
- Production is read-only. Any prod change is typed by a person.
- No AI attribution lines in commit messages. The human is the sole author.
- Verified vs inferred, always. Tag every claim with its source or say it is a guess. Do not manufacture findings.

## Models
- The most capable model handles reasoning and research. Spend its tokens where deduction matters.
- Delegate simpler, bulkier work (QA runs, sweeps, first-pass review) to a cheaper model via subagents.

## Knowledge map (read both before substantive work)
- `mother-context.md`: volatile project state. Current situation, plan, tickets, decisions in flight, open questions, dated log. Revise in place after anything that changes the picture. Do not append.
- `domain-knowledge.md`: durable reference and provenance. How the domain works, systems and their aliases, data flows, spec facts. Each claim source-tagged and confidence-flagged. Update only when a mechanic or its source changes.
- Boundary rule: a settled fact about how the world works goes in `domain-knowledge.md`; the current state of our work or an open question goes in `mother-context.md`. When they conflict, `domain-knowledge.md` wins on mechanics, `mother-context.md` on what is happening now.

## Sources
- Search every available source before concluding: the code, the issue tracker, chat history, docs, the database (read-only). Say which you used.
