# PHASE 2 — EVALUATION (weeks 4–6) ⭐ CENTRAL PHASE

This is the skill that makes me employable and the one where most candidates are hollow.
Three weeks, owned — but the effort goes into **building the harness**, not into
manual annotation.

**2.1 The harness on public datasets.** Runners for BEIR, HotpotQA, SQuAD 2.0, QASPER. Metrics
**separated between retrieval and generation** — this is the key technical point and a frequent
interview question. Retrieval: recall@k, precision@k, MRR, nDCG. Generation, assuming perfect
context: groundedness, relevance, citation accuracy, correct refusal rate on the
unanswerables, over-refusal rate. End to end: accuracy, latency, cost.

What each dataset is for (plan of 2026-11-05). BEIR (SciFact, NFCorpus, FiQA): retrieval
alone, against published nDCG@10. SQuAD 2.0: generation on the gold paragraph, for the
refusal and over-refusal rates; its published scores are those of fine-tuned extractive
readers, shown for reference, not as a target. HotpotQA: the full-wiki corpus (5.2 million
passages) does not fit a local pgvector, so the paragraphs of 1,000 questions of the
distractor setting are pooled into one corpus (9,789 paragraphs). Verified when the loader
was written (2026-11-05): no published score applies to such a pool (BEIR measures the
full corpus, the distractor leaderboard ranks readers that are handed the ten paragraphs),
so its arms are compared with each other, gold context against retrieved context, not with
the literature. QASPER: a question is about one paper, so retrieval is scoped to that
paper, as the dataset defines the task; unscoped, the question "which approaches do they
compare with?" retrieves another paper's chunks and the answer is a refusal (notebook 2,
full run of 2026-11-05). A QASPER question is kept when its annotators agree on whether it
can be answered and, if it can, when at least one paragraph of text supports it (evidence
that is only a table or a figure is out of reach of a text pipeline): 887 of the 1,005
validation questions.

**2.2 Comparison with the literature.** For each dataset, our score next to the published
scores. A large gap is a bug, not a result: treat it as such. First benchmark obtained in
phase 1: the harness must reproduce the nDCG@10 measured via `mteb` on SciFact
(bge-base-en-v1.5 0.740; all-MiniLM-L6-v2 0.645; BM25 0.686 through `mteb/baseline-bm25s`,
the rerunnable lexical reference since 2026-11-04, next to the BEIR paper's Anserini 0.665).
A published score is reproduced under its own conditions (whole documents, exact search),
then the phase 1 system is measured as built (chunks, HNSW): two rows, never one.

**2.3 LLM-as-judge, done right.** Explicit rubrics, discrete scoring, justification
before the score, a judge model different from the generator (OpenAI, the generator being
Anthropic — ADR 006). **Calibration is mandatory**: I annotate 50 examples by hand, you measure
the agreement (Cohen's kappa). An uncalibrated judge is a generator of reassuring numbers.
Neutralize and document the biases: position, verbosity, self-preference, format.

**2.4 Non-determinism.** N runs, bootstrap confidence intervals. Without that, phase 3
will celebrate +2% gains that do not exist.

**2.5 The in-house corpus — a single corpus, three uses.** A few hundred raw documents,
selected on **two criteria and two only**: published after the cutoffs of the models
used, and hard to parse (columns, tables, scans, footnotes, irregular
structures). **The topic does not matter — do not propose a domain for me to understand,
propose formats to break.** This corpus serves simultaneously to: measure contamination
by comparison with the public datasets, support the in-house golden set, and provide the
poisoned documents of phase 7. Propose 3 candidates to me with their format difficulties and
their license (the repo is public: the license must allow redistribution, or the corpus is
downloaded by script without being versioned).

PDF parsing is measured in phase 3, but this corpus is ingested here: phase 2 adds one
deliberately naive text extractor, the baseline phase 3 has to beat, and the golden set is
written against a reference text of each document, not against that naive extraction, so
that the same questions can later judge a parser. "Published after the cutoffs" is a dated
property: the manifest of the corpus records the freshness floor and the models it holds
for, and a model upgrade can void it.

**2.6 The in-house golden set — 50 to 80 questions, no more.** Its purpose is not volume, it is
to show that I can build an evaluation from scratch: labeled taxonomy
(factual, multi-hop, **unanswerable**, ambiguous, trap, temporal: reasoning over dates
stated in the documents, not freshness of the index, the corpus being static), assisted
generation then
full human review through a CLI that you build for me, versioning with a CHANGELOG. It is
also the reusable foundation if I ever plug it into a client's data (in a separate
repo).

**2.7 Industrialization.** `make eval` → comparative HTML report, run history in the database.
**Regression guard**: we work on `main` without PRs (ADR 008), so there is no PR to
block. Two levels instead: (1) a `pre-push` hook that runs `make eval-gate` in sample
mode and **rejects the push** beyond the regression threshold — this is the only real block;
(2) the same gate in GitHub CI, which turns red on `main` if the hook was bypassed.
The notebook must state honestly the difference from a blocked merge in a team.
In sample mode the models are simulated and the datasets are fixtures: the gate guards the
**code paths** (a loader, the chunker, a search mode, a metric), not the quality of a model
or a prompt. That second guard is the full run: `make eval` compares each arm, query by
query, with the archived run it replaces and says whether the difference is significant.

Look at what Ragas, promptfoo and DeepEval do — but **build ours first**, then
compare in the notebook.

**Notebooks**: (1) measuring a RAG — why end-to-end metrics hide the real
problem; (2) LLM-as-judge: calibrate it or do not use it; (3) contamination — why
your good scores may be lying; (4) building a golden set from scratch, small.

**Key deliverable**: the **measured baseline** of the phase 1 system, compared with the
literature.
