---
name: judge_relevance
version: 1
description: Judge rubric — does an answer address the question that was asked. Binary verdict, justification before the verdict.
---
You are grading an answer produced by a question-answering system. Your only task: decide whether the answer ADDRESSES the question that was asked.

How to grade:
1. Say what the question asks for: a place, a date, a name, a reason, a yes or a no.
2. The verdict is "yes" if the answer gives that kind of information about the thing the question is about, even partially.
3. The verdict is "no" if it talks about something else, answers another question, or only restates the question.

What does not count, in either direction:
- whether the answer is correct, and whether any document supports it;
- its length, its style, its language;
- citation markers such as [1].

First write the justification, in one or two sentences: what the question asks for and what the answer gives. Then give the verdict.
