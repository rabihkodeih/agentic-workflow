# agentic-workflow

How I actually work with AI coding agents, day to day, on a production codebase. Not a demo, not a benchmark. This is the setup I run against a revenue-carrying Django platform (automotive retail, OEM integrations, lots of legacy), and it is the reason I ship more tickets than anyone on my team this year while still owning every line that goes to production.

The short version: the model is not the hard part. The harness is. Context, guardrails and a repeatable loop are what turn a chat window into an engineer you can leave alone for an hour.

Everything here is sanitised. No employer code, no client names, no internal ticket keys. The skills are the real ones with the specifics swapped out.

## What is in here

```
README.md                 this write-up
context-repo-template/    skeleton of a per-project context repo, copy it and go
skills/                   fifteen Claude Code skills I use daily, generalised
```

## 1. The context repo

Every project I touch gets its own small git repo next to the code repo. Not inside it. The code repo belongs to the team; the context repo is mine and the agent's.

It has three kinds of files and the split is by how often they change:

| File | Changes | Holds |
|---|---|---|
| `AGENTS.md` | almost never | rules of engagement, knowledge map, what the agent may and may not do |
| `mother-context.md` | every session | current state: plan, tickets in flight, decisions, open questions, a dated log |
| `domain-knowledge.md` | rarely | how the domain works, each claim tagged with where it came from and how sure I am |

Plus `outbox/` for anything drafted for a human that has not been sent, `plans/` for per-ticket plan files (deleted once merged), and `human-notes.txt` which the agent is told never to edit.

The boundary rule between the two big files is the thing that keeps it working: a settled fact about how the world works goes in `domain-knowledge.md`, the current state of my work goes in `mother-context.md`. When they disagree, domain knowledge wins on mechanics, mother context wins on "what is happening now".

The template is in [`context-repo-template/`](context-repo-template/). The files are short on purpose. `AGENTS.md` routes to the knowledge files, it is not itself the library.

## 2. The daily loop

Same thing every day, in this order:

1. Fresh session. Never continue yesterday's.
2. `/ingest-context`: the agent reads `AGENTS.md`, `mother-context.md`, `domain-knowledge.md` and says back where things stand.
3. Feed in what happened overnight: Slack threads, emails, Jira comments. MCP servers for Jira, Confluence, Slack, SonarQube and AWS mean the agent can pull most of this itself.
4. Grill it. "What changed, what is blocked, what would you do first." If the answer is wrong, the context is wrong, fix the context before doing any work.
5. Do the work. Plan file per ticket, implement, run tests locally, self-review, QA test cases, QA run.
6. Drafts for every open thread go to `outbox/`. I read them, I send them.
7. Update `mother-context.md` in place. Revise sections, do not append.
8. Close the session.

Once a week or so, `/cleanup-context`: prune closed items, promote durable facts into `domain-knowledge.md`, compress the log to one line per milestone. Git history keeps the rest.

## 3. Guardrails

These are hard rules in every `AGENTS.md`. They are not about trust in the model, they are about who is accountable when something goes wrong. That is me.

- **Humans own all communications.** The agent drafts, I send. Slack, email, Jira comments, PR replies, all of it.
- **Production edits are human-only.** Prod DB skills are read-only and enforced server-side. Prod config in admin tools is typed by a person.
- **Commits and pushes are mine.** The agent stages nothing without being asked and never pushes.
- **Never edit `human-notes.txt`.** A place for me to leave notes the agent reads but cannot touch.
- **Verified vs inferred, always.** Every claim in a report says which it is and where it came from. No manufactured findings to look thorough.

The last one matters more than the others. An agent that is allowed to guess quietly will poison the context repo within a week.

## 4. Skills

Skills are the repeatable procedures, written once and invoked with a slash command. The fifteen in [`skills/`](skills/) are the ones I run most. The first twelve, read top to bottom, are the loop: ingest, work, test, commit, PR, Sonar, review comments, change summary, worklog.

| Skill | What it does |
|---|---|
| `ingest-context` | load the context repo at session start |
| `cleanup-context` | aggressive prune of the context files, promote durable facts, fix dangling references |
| `generate-test-cases` | manual QA test cases from the branch diff, in a fixed table format, with a coverage checklist |
| `handle-code-review-comments` | walk unresolved human PR comments one at a time, propose a fix, ask, optionally reply |
| `change-summary` | the change-advisory section a release board wants: description, risk, coverage from Sonar, DB changes, revert strategy |
| `prod-db-postgres` | read-only SQL against a private production Postgres over a per-call SSM port-forward; guard client-side, `default_transaction_read_only` server-side |
| `prod-db-mysql-bastion` | same idea for a MySQL/Aurora proxy with no public endpoint: the runner is piped to an EC2 in the VPC over SSH-via-SSM, credentials come from Secrets Manager on the box and never touch the laptop |
| `redash` | Redash REST client, stdlib only: saved queries, ad-hoc SQL with a read-only guard, dashboards, API key from the keychain |
| `log-worklogs` | Jira worklogs from a pasted bullet list, via the Atlassian MCP; totals sanity-checked before anything is posted |
| `commit-workflow` | conventional commits with a WHY line in the body, ticket code from the branch name, logical staging |
| `pr-workflow` | create or update the PR with `gh`, following the repo's PR template, ticket-prefixed title |
| `sonar-workflow` | Sonar issues for the PR in priority order: trivial smells fixed and verified automatically, hotspots and blockers one by one with approval |
| `short-answer`, `yes-no`, `lazy-reply` | answer-style toggles. Stacking `/short-answer` tightens the answer a notch each time; `/yes-no` puts the verdict first; `/lazy-reply` is the busy-colleague register, lazy about presentation and never about thinking |

The prod-DB skills are the ones I am most careful with. Both refuse anything that is not a read statement before touching AWS, and both make the server enforce it again, because a regex is not a security boundary and a storage engine is. Each ships an offline guard test. Every SKILL.md also tells the agent to ask a human before the first query of a session.

Things I run but cannot publish: a skill that files my monthly tax declaration on a government portal, and a "write in my voice" skill built from a corpus of my own messages, banned-word list included.

Install a skill by dropping its folder into `~/.claude/skills/`.

## 5. Integrations

The agent is only as useful as what it can see. These are wired in through MCP servers or the CLI, and the rule for every one of them is the same: read freely, write only what a human asked for, never send.

| System | How | Used for |
|---|---|---|
| Jira, Confluence | Atlassian MCP | read tickets and comments at session start, search docs, post the change-advisory section to a ticket on request, log worklogs from my daily notes |
| Slack | Slack MCP | read threads and channels for context; replies are drafted to `outbox/`, never posted by the agent |
| GitHub | `gh` CLI | PR state, unresolved review threads, CI status, replying to a reviewer only after I approve the text |
| SonarQube | Sonar MCP | quality-gate status and the coverage number for the change summary, issue lists for the fix loop |
| AWS | AWS MCP plus the prod-DB skills | CloudWatch forensics, SSM parameters, instance state, read-only production queries |
| Playwright | Playwright MCP | executes the generated manual test cases against a running build and reports pass/fail |
| Redash | the `redash` skill | numbers from the analytics warehouse without touching the primary |

Two personal projects push the same ideas further. [unreal-atlas-mcp](https://github.com/rabihkodeih/unreal-atlas-mcp) is an MCP server for Unreal Engine 5 built code-execution-first: one `execute_python` tool that runs a script inside the editor, plus ten helpers, instead of a catalogue of hundreds of fine-grained tools. [godot_game](https://github.com/rabihkodeih/godot_game) is a Godot 4 horror prototype built with a director/worker pipeline: the director model writes contracts and reviews, worker agents get one contracted micro-task each, and a headless verification suite is the only merge gate.

The Jira and Slack ones changed my day the most. Session start used to be twenty minutes of reading. Now the agent pulls the overnight threads, the ticket comments and the CI results, and I start from a summary I can interrogate.

## 6. Models and delegation

Rules in `AGENTS.md`:

- The most capable model does the reasoning and the research. Its tokens are spent where logic and deduction actually matter.
- Subagents run on a cheaper model by default. QA runs, test-case generation, sweeps across many files, first-pass reviews.
- Review is layered: agent first pass, then a review bot on the PR, then I rebuild and run the tests locally before I approve anything. I am reviewer of record for the team, the AI is not.

## 7. What it changed

Qualitative, because I do not have a clean before/after:

- I stopped losing the thread between sessions. The context repo is the memory, not the chat.
- Communications got better, not worse. Every reply is drafted with the full history in front of it, then read by a human before it goes out.
- Cutovers, migrations and incident write-ups now come with a plan file, a QA report and a parity number. Before, they came with a Slack message.
- Throughput went up a lot. I authored the majority of my team's new tickets this year and closed the most. I would not have kept up with the lead-routing programme I run without this.

What it did not change: I still read every diff. The model is fast and confident and wrong often enough that the local rebuild-and-test step stays.

## 8. Things I got wrong first

- Letting the agent append to `mother-context.md` instead of revising it. The file became a log nobody read. Revise in place, keep the log as a table at the bottom.
- One context repo for several projects. They bleed into each other. One per project.
- Skipping the ingest step to "save tokens". Costs more every time, the agent re-derives things it already knew and gets some of them wrong.
- Trusting a number the agent produced without a source line. Now every number in a report carries `(src: file:date)` or it does not go in.

## Licence

MIT. Take what is useful.
