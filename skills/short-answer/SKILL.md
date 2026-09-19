---
name: short-answer
description: Answer the user's question as concisely as possible, a direct, to-the-point response with no preamble, filler, or unnecessary elaboration. Use when the user types "/short-answer", asks for a brief/short/concise/TL;DR answer, or says "just the answer".
---

# Short Answer

Give the most direct, to-the-point answer possible.

Rules:
- Lead with the answer. No preamble ("Great question", "Sure", "Let me…") and no restating the question.
- Prefer one sentence. Use a short list only if the answer genuinely has multiple parts.
- No background, caveats, or elaboration unless they are essential to the answer being correct.
- If the answer is a single value, name, command, or yes/no, return just that, optionally with a few words of context.
- If the question is ambiguous enough that a short answer would be wrong or misleading, ask one brief clarifying question instead of guessing.
- Code: return only the relevant snippet, not a full explanation, unless asked.

## Stacking

Extra `/short-answer` prefixes arrive as literal text in the arguments. Each one tightens the answer another notch, strip the prefixes, answer the remaining question at the corresponding level:

- `/short-answer <q>`, one sentence.
- `/short-answer /short-answer <q>`, one phrase or clause. No verb required.
- Three or more, one word, number, name, or symbol. Nothing else.

Truncate, never distort: if the question genuinely cannot be answered at the requested level without being wrong, answer at the tightest level that is still correct.

Keep it tight. The user invoked this skill because they want the signal, not the noise.
