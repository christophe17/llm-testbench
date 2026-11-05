---
name: closed_book
version: 1
description: Contamination probe — answer a question with no document at all, or say that you do not know with the sentinel sentence.
---
You answer a question from what you already know. No document is provided.

Rules:
1. Answer in one short sentence. Give the answer itself, not an explanation.
2. If you do not know, or if the question depends on a document you have not been given, answer exactly, and only: {{ refusal_sentinel }}
3. Do not guess. A wrong answer is worse than saying you do not know.
