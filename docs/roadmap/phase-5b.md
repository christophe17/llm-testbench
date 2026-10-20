# PHASE 5B — The bridge: classical ML or LLM, the answer is a table (~1 week)

Added on 2026-08-31 (ADR 005). The "B" means "inserted after the fact between 5 and 6", not
"subpart of phase 5".

Purpose: measure, with the existing harness, the trade-off between a classical ML model, an
LLM and a hybrid on the **same task**. It is the only deliverable of the project where we train
a classical model, and it exists only as a comparison arm: we do not build a prediction
system, we quantify an architecture choice. It is the bounded exception of `CLAUDE.md` §6.

**Datasets decided (ADR 005)**: tabular `fake_job_postings2` (EMSCAD via the AutoGluon
multimodal benchmark, CC BY-NC-SA copy — **never redistributed**; original site dead,
upstream license unverifiable) and text **Banking77** (CC BY 4.0, loaded without the HF script).
Documented substitutes if one breaks: `women_clothing_review`, MASSIVE fr-FR.

**5B.1 Tabular task with free text** (fake_job_postings2). Mandatory arms, all measured
by the same runner:

- dumb baseline (`DummyClassifier`, majority and stratified strategies);
- a simple rule (a single attribute, a single threshold — a depth-1 tree);
- gradient boosting **with the text ignored**;
- gradient boosting **with the text as TF-IDF n-grams** — the classical hybrid, mandatory:
  without it the LLM hybrid is compared to a straw man (literature on fake_job_postings: 0.968
  versus 0.926 for the embedding hybrid);
- zero-shot LLM on serialized rows (serialization template in a versioned file in
  `prompts/`, validated structured output), then in-context few-shot at a fixed k (stratified
  examples, identical for all rows, fixed seed);
- hybrid: embeddings of the text fields by the phase 1 provider, injected as
  features into the gradient boosting.

A single LLM model per arm, chosen for what we would really deploy at this volume; the model
is a parameter of the notebook, not a dimension of the table.

**5B.2 The reverse case: text classification** (Banking77). Dumb baseline · TF-IDF +
linear model · embeddings + linear model (the "middle": semantics without generation) ·
zero-shot LLM with the list of labels in the prompt · few-shot LLM. Expectation declared
before measurement: a small quality gap for a cost gap of several orders of magnitude. If the
measurement contradicts the expectation, that is the result, and we publish it.

**5B.3 Measurement axes, all in the table:**

- quality: the dataset's metric (AUC / macro F1), N runs, bootstrap interval — compared with
  the published score;
- p95 latency per prediction and batch throughput;
- cost per thousand predictions: amortized training + inference for the classical model,
  tokens × price via the phase 5 instrumentation for the LLM; effect of the prompt cache (the
  label list and the few-shot examples are a constant prefix);
- determinism: prediction-by-prediction agreement rate between two identical runs (fixed
  seed for the classical model; temperature 0 for the LLM — the number is not 100%, that is
  the point);
- reproducibility: what must be pinned to replay the number in six months (versions,
  seeds, exact model identifier — an API model can change without notice, see the
  phase 5 runbook), materialized by a **run manifest** that the runner writes next to
  the results — hashed config, seed, dataset revision, versions, exact model
  identifier, metrics, cost; **without a manifest, a training number does not enter
  the table**;
- auditability: existence of a **per-prediction** explanation that a third party can
  recompute (SHAP / coefficients) versus a generated justification; a single quantified proxy:
  stability of the LLM justification on the same replayed input;
- defensibility before a regulator: a discrete grid (0/1/2) with explicit criteria, grounded in
  the transparency obligations of the AI Act and GDPR Art. 22, declared qualitative, linked
  to `docs/ai-act.md` from phase 7.

**5B.4 Contamination.** Public tabular datasets are old and ubiquitous on Kaggle: the
LLM zero-shot is probably inflated. Apply the contamination signal measurement of
phase 2 and write it next to the number. Imperfect and documented literature reference:
TabLLM does few-shot fine-tuning, not in-context few-shot — only its zero-shot is
comparable to our arm.

**5B.5 Key deliverable**: `docs/decision-tree-ml-vs-llm.md`, an architecture decision tree
where **each branch cites a number from the table** — when a rule is enough, when classical ML,
when the hybrid, when the LLM (little labeled data, shifting labels, long and
rare text) — plus the volume threshold where the cost tips over. The tree goes into the
phase 8 README.

**Guardrails**: a `src/llm_testbench/classic/` module (classical models, row
serialization, hybrid features), tested and typed, **never exposed by the API nor called by
the agent**; the runners extend `eval/`. Default hyperparameters or a bounded, documented
search — no score hunting. No feature store, no drift, no retraining, no model
matrix, no second task.

**Notebook**: "choosing between an XGBoost and an LLM, the answer is a table" — the visible
intermediate outputs are the serialized row, the final prompt, the raw response and its
parsing, the SHAP explanation of a prediction, and the table.
