---
name: golden_unanswerable_check
version: 1
description: Second reading of a draft marked unanswerable — does the whole paper contain the answer after all; the passage is copied exactly so that code can check it.
---
You are given the full text of a research paper and a question about it. Someone who read only the beginning of the paper claims the paper does NOT contain the answer. Check that claim against the whole text, tables and appendices included.

- If the paper states the answer, set "answered" to true, give the answer in one sentence, and copy EXACTLY, character for character, the one or two sentences (or the table row) that state it.
- If the paper does not state the answer, set "answered" to false and leave "answer" and "quote" empty. A passage on the same topic that does not give the answer does not count.

Do not use anything you know from elsewhere: only what this text states.
