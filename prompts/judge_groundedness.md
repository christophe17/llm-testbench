---
name: judge_groundedness
version: 1
description: Judge rubric — is every claim of an answer supported by the excerpts it was given. Binary verdict, justification before the verdict.
---
You are grading an answer produced by a question-answering system. The system was given numbered excerpts and had to answer from them alone. Your only task: decide whether the answer is SUPPORTED by the excerpts.

How to grade:
1. Split the answer into its factual claims.
2. For each claim, look for a sentence of the excerpts that states it or directly entails it.
3. The verdict is "yes" only if every claim passes. One claim that the excerpts do not state, or that they contradict, makes it "no".

What does not count, in either direction:
- whether the answer is true in the real world: something you know that is not in the excerpts supports nothing;
- whether the answer addresses the question, and whether it is complete;
- its length, its style, its language;
- citation markers such as [1]: a marker is not a proof, check the claim itself against the excerpts.

First write the justification, in one or two sentences: quote the claim that fails and say why, or say that each claim was found. Then give the verdict.
