# Domain knowledge: <project>

> **Durable reference layer.** Slow-changing facts about how the domain works and where each fact came from. Authoritative for mechanics; project state lives in `mother-context.md`. In a workspace family, the root's copy is the maintained one; clones promote findings back.

## How to read this file
- Format: claim. (src: <tag>) [verified | inferred | unknown]
- Source tags: `code: <repo>/<path>:<line>` · `issue <KEY>` · `doc <id or url>` · `chat <channel> <date>` · `pr <repo>#<n>` · `ci <run id>` · `db <name> <date>` · `sibling: <workspace> §X` (carried over, not re-verified here).
- Confidence: **verified** read from a primary source · **inferred** synthesis · **unknown** not yet checked.

## 1. People and roles (volatile; re-check before relying on it)
- Name, role, what they own or decide. (src: ...) [verified]

## 2. Systems and aliases
- System A, also called "X" in chat and "Y" in the DB. (src: ...) [verified]

## 3. Environments, hosts, access
- ...

## 4. Build, test, release, deploy
- ...

## 5. How data flows
- ...

## 6. Spec facts
- ...

## 7. Gotchas
- ...

## 8. Source legend
- Code: where each repo and package lives (see `AGENTS.md` "Code").
- Skills and scripts that already encode mechanics: ...
