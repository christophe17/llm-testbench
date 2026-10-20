# ADR 005 — Phase 5B "The bridge": measuring the classic ML / LLM trade-off

- **Date**: 2026-08-31
- **Status**: accepted

## Context

The testbench measures LLM techniques against each other; it never says when an LLM is the
wrong answer compared to a classic model, even though that is the first question asked
in a system design interview and the costliest decision in production. Section 6
of the brief forbids prediction and business modeling — a protective rule against
drifting into a second project, but one that, read literally, also forbids measuring this
trade-off. The brief also requires a single harness and a single system.

## Options considered

1. **Do nothing** — consistent with the rule, but leaves a hole in the
   "I choose an architecture on evidence" argument; the trade-off would remain an opinion.
2. **A short phase (5B) that extends the harness** — the classic model exists only
   as a comparison arm; the section 6 rule is reworded with a named exception
   and three locks. Cost: ~1 week, ~$20–50 of API with a "mini" model
   (~$300 with a frontier model — hence a single model, stratified sampling of the
   test split if it is expensive), one dependency (xgboost + shap, arm64 wheels available).
3. **A separate "classic ML vs LLM" repo** — violates "never a second project" and
   would lose the cost/latency instrumentation and the harness bootstrap.

## Decision

Option 2. Phase 5B after phase 5 (it consumes its cost/latency instrumentation — it
is its first external client, which tests the abstraction), before phase 6
(which will replay its LLM arm self-hosted). Numbering kept: renumbering 6–10
would break the references in ADRs 001–003, JOURNAL and STATE for zero gain; the
"B" means "inserted after the fact", not "subpart of 5".

Two tasks, one tabular with free text and one text classification, on public
datasets with a published reference. Mandatory arms: dumb baseline, simple rule, GBM
with text ignored, **GBM + TF-IDF n-grams** (without it the LLM hybrid would be compared to a
straw man — Shi et al. 2021 measure on fake_job_postings: GBM without text AUC 0.697,
GBM + n-grams 0.968, GBM + embeddings 0.926), zero-shot and few-shot in-context LLM,
embeddings → GBM hybrid. A single LLM model per arm. Axes: quality with bootstrap CI,
p95 latency, cost/1,000, determinism, reproducibility, auditability, defensibility
(the last two on a discrete grid declared qualitative + one measured proxy each).
Deliverable: `docs/decision-tree-ml-vs-llm.md`, each branch backed by a number.
Module `src/llm_testbench/classic/`, tested and typed, never exposed by the API nor called
by the agent.

## Datasets — verification of 2026-08-31, decided the same day

Phase 0 protocol (availability, size, license, redistribution). No data
is versioned in the repository. **Selected: `fake_job_postings2` and Banking77.** The
other columns remain as documented substitutes if a loading path breaks.

**Tabular with free text** (reference: AutoGluon multimodal benchmark, Shi et al.
2021, NeurIPS D&B; copies hosted on S3 `automl-mm-bench`, HEAD 200 verified, sha1
in the original loader; license of the copies CC BY-NC-SA):

| | fake_job_postings2 (EMSCAD) — **recommended** | women_clothing_review | employee_salaries |
|---|---|---|---|
| Task | binary (fraud, ~5% positives), ROC-AUC | rating regression 1–5, R² | salary regression, R² |
| Size | 12,725 / 3,182, 21 MB | 18,788 / 4,698, 4 MB | 9,228 rows, 1.3 MB |
| Text | title, description, requirements (long, real) | title + review | job title (385 short values) |
| License | NC copy; original EMSCAD site dead (generic hosting page); Kaggle copy unverifiable without an account | NC copy; Kaggle original announced as CC0; HF mirror `Censius-AI` Parquet | **CC0 confirmed** (OpenML API 42125) |
| References | GBM without text 0.697 · + n-grams 0.968 · pre-embedding 0.926 · Text-Net 0.963 · stack 0.964 | without text 0.001 · + n-grams 0.654 · pre-embedding 0.642 · stack 0.751 | skrub docs: MinHash + HGB R² 0.911 ± 0.014 |
| Verdict | only dataset where tabular **and** text both carry signal; fraud → audit/regulator axes make sense; probable contamination (2014) | tabular alone ≈ 0: the hybrid measures text against text | 3-word "text"; regression |

Rejected: `product_sentiment_machine_hack` (tabular = one column, license not found).
Methodological reference for the zero-shot arm: TabLLM (Hegselmann 2023, AISTATS) — its
few-shot is fine-tuning, **not comparable** to our in-context few-shot.

**Text classification**:

| | Banking77 — **recommended** | MASSIVE fr-FR | AG News |
|---|---|---|---|
| Task | 77 banking intents, 10,003 / 3,080 | 60 intents, ~11.5k / 2k / 3k (fr-FR locale) | 4 topics, 120k / 7.6k |
| License | CC BY 4.0 | CC BY 4.0 | "non-commercial research", HF: unknown |
| Loading | HF `PolyAI/banking77` script-based → broken (`datasets` ≥ 3); Parquet PR `refs/pr/6` (2025-08), mirror `gtfintechlab/banking77`, or PolyAI GitHub CSV | `AmazonScience/massive`, native Parquet | native Parquet |
| References | fine-tuned BERT 93.66% (83.42% at 10 ex./intent), USE 92.81%; zero-shot LLM 10–25 pts below | XLM-R base 86.3%, mT5 87.2%; MTEB `MassiveIntentClassification (fr)`: embeddings + linear published per model | TF-IDF n-grams 92.36% (Zhang 2015) |
| Verdict | richest LLM-vs-fine-tuned literature; 77 labels in the prompt amplify the cost gap and make the prompt cache measurable | the testbench's only French-language task; direct reference for the "embeddings + linear" arm | too easy, unclear license — rejected |

## Consequences

The README gains the "when not to use an LLM" argument, quantified. Section 6
carries an explicit exception; any reuse of the `classic/` module outside 5B is
a violation, not an extension. The chosen datasets are old and ubiquitous:
contamination measured (phase 2), not ignored. Expectation declared before measurement for the
text task (small quality gap, cost gap of several orders of magnitude) — the
Banking77 literature suggests it will not hold as is on 77 fine-grained
intents; that will be a branch of the tree, not a result to dress up.
To revisit if phase 5 does not deliver a per-call cost reusable outside its
context.
