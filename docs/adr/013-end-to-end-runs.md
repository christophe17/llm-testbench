# ADR 013 — End-to-end runs: the same questions on the gold context and on the retrieved one

- **Date**: 2026-11-05
- **Status**: accepted

## Context

Phase 2.1 asks for metrics "separated between retrieval and generation" and, end to end,
accuracy, latency and cost. ADR 011 measures retrieval alone (a ranking against judgments),
ADR 012 measures generation alone (answers on the gold passages of SQuAD 2.0). Neither says
what the phase 1 system does when both are chained, and an end-to-end score alone cannot say
which of the two failed. Two datasets were still to be wired: HotpotQA and QASPER.

## Decisions

**1. One generation runner, three contexts.** `run_generation` takes a `ContextProvider`
(`eval/context.py`): the **gold** passages, the chunks **retrieved** by the system's own
document source, or **nothing** (the closed-book probe of phase 2.5). The same questions
are asked on each, with the same prompt and parser as the API. The retrieved context goes
through `DocumentSource`, split into "embed the question" and "search a vector" so that
the harness records the cost and the duration of each. Rejected: a second runner that
calls the HTTP API. It would measure the same code plus a network hop, need a running
service in CI, and lose the per-step timings; the HTTP path is the business of the load
tests of phase 5.

**2. A failure is charged to the search or to the generator.** An end-to-end answer also
records whether each gold passage was among the chunks handed to the generator
(`context_recall`, and `context_complete` when all of them were). A gold passage is cut by
an annotator and a chunk by a size, so "found" is defined on the text: a retrieved chunk of
the right document that holds at least half of the passage in one piece. The answerable
questions are then split four ways, passages found or not, reference answer given or not
(`attribution`). Rejected: matching chunk identifiers (a gold passage is not a chunk);
exact containment only (a chunk boundary through a passage would read as a miss); a
similarity threshold between embeddings (it would judge the search with the search).

**3. HotpotQA is measured on a pool, and compared with itself.** The full-wiki corpus
(5.2 million paragraphs) does not fit a local pgvector. The distractor setting gives each
question ten paragraphs; the paragraphs of 1,000 questions, drawn once with a fixed seed,
are pooled into one corpus of 9,789. One loader, two views: a retrieval dataset (which
paragraphs come back) and a question-answering dataset (what is answered). Checked when
the loader was written: no published score applies to such a pool, since BEIR measures the
full corpus and the distractor leaderboard ranks readers that are handed the ten
paragraphs. Its arms are compared with each other. The roadmap said "chosen for having
published recall@k, to be verified": verified, and corrected there.

**4. QASPER keeps the questions a text pipeline can be scored on.** A question is kept when
its annotators agree on whether it can be answered and, if it can, when at least one
paragraph of text supports it: 887 of the 1,005 validation questions (9% of the evidence
points at a table or a figure, which the text does not contain). The search is scoped to
the question's paper through a metadata filter, as the dataset defines the task. An
unanswerable QASPER question names no passage: it is asked on the retrieved context only,
and the gold-context arm reports how many questions it left out.

**5. The scoped search was checked against an exact one before being trusted, and no
search mode was added.** A filter and an approximate index do not compose by themselves:
HNSW returns its nearest candidates and the filter is applied afterwards, so a selective
filter can return fewer rows than asked, or none. On the 887 QASPER questions the scoped
search returned exactly the chunks of an exact search, five each time. `EXPLAIN` shows why:
Postgres reads the documents that pass the filter first, then compares their chunks one by
one, and does not use the HNSW index at all. An `iterative` and an `exact` mode were
written for `PgVectorStore.search`, measured identical, and removed. The risk is not gone:
the plan depends on the planner's statistics, and a filter that keeps many documents may
go through the index. pgvector's iterative scans (0.8 and later) are the known answer; to
be measured in phase 3 if filters come into play there.

**6. One event loop per command.** `make eval` ran its retrieval arms and its generation
arms in two `asyncio.run` calls; the HTTP client of the first was closed on a loop that no
longer existed. Both now run on one loop: a connection pool belongs to the loop that
opened it.

**7. One output cap for the API and the harness, and a cut answer is counted.** The
generator reasons before it writes (adaptive thinking, on by default on the current Claude
models), and those tokens are output tokens: billed, counted against the cap, absent from
the text. The harness capped a call at 512 tokens and the closed-book probe at 120, both
sized for the visible answer: 9 answers in 100 came back cut on QASPER, and 56 in 100
came back **empty** on the probe, with a finish reason of `length` and no error. The API
had its own cap, 1,024. There is now one constant (`generation/answer.py`,
`MAX_OUTPUT_TOKENS = 4096`), used by both, sized as a safety net and not as an answer
length; every answer records whether it was cut, and every run reports the share
(`truncated`). A cut answer stays in the rates: it is what the system returned. Rejected:
lowering the reasoning effort to make answers fit, which changes the system under
measurement; it is a cost lever to measure on its own (phase 3). The judge and the drafter
of the golden set, OpenAI models that reason too, get the same room.

## Consequences

- Sizes follow the budget of ADR 012: 100 questions per generation arm, so a rate is known
  to about ±0.10. The retrieval arms of the pool run on all 1,000 questions.
- The arms measured before decision 7 were capped at 512 tokens. Those where the cap bit
  were run again (QASPER on both contexts, the three closed-book probes). Three were kept
  as archived, with one answer in a hundred or fewer at the cap: SQuAD 2.0 on the gold
  context (2 calls in 200), whose answers are already in the calibration set being
  labelled, and HotpotQA on both contexts (0 and 1 in 100).
- Cost was underestimated twice for the same reason: an answer of 60 visible tokens is
  billed 120 to 400. Estimates now start from measured output tokens, not from the length
  of the text.
- `contains_answer` is the only measure of correctness without a judge, and it is rough:
  lenient on a yes-or-no reference, blind to a right answer worded differently (a third of
  the QASPER answers are free-form sentences). It reads as a lower bound on QASPER. A
  judge rubric for correctness against the reference answer comes with the judged
  baseline, after the calibration.
- The gold context and the retrieved one are not the same amount of text: five chunks of
  1,000 characters against one or two paragraphs. A difference between the two arms mixes
  what the search missed with what the extra text distracted.
- The first end-to-end run found a defect of phase 1 that no retrieval metric shows: on
  the freshly built HotpotQA index the API's chunk search took 22 seconds. The shared
  `documents` and `chunks` tables had been analyzed before the load, the planner expected
  one row for the new source and joined 10,635 chunks against 4,896 documents each. The
  ingestion pipeline now ends a load with `ANALYZE` (`PgVectorStore.analyze`). Autovacuum
  would not have done it: the load was under a tenth of the tables.
- The gate runs each new code path on fixtures: 11 arms, HotpotQA and QASPER on both
  contexts.
