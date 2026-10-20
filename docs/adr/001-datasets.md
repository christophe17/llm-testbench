# ADR 001 — Testbench datasets and starter dataset

- **Date**: 2026-08-26
- **Status**: accepted

## Context

The brief lists ~15 candidate datasets, drawn from a model's memory. A complete web
verification (name, version, license, size, retrieval method — details in
`docs/datasets-verification-2026-08-26.md`) confirmed most entries and invalidated
or qualified some. Tooling constraint: `datasets` ≥ 3 no longer runs HF loading
scripts — only native Parquet repositories load cleanly.

## Decisions

1. **Phase 0 reference dataset: BEIR/SciFact.** 5,183 documents, 300 test queries,
   near-binary qrels, 4.5 MB, native Parquet, abundant literature (BM25
   nDCG@10 ≈ 0.67-0.69). NFCorpus is smaller on disk but its ~134k graded qrels
   complicate harness validation — SciFact first, NFCorpus and FiQA in phase 2.
2. **Natural Questions removed.** ~145 GB for an indirect "no answer" signal;
   SQuAD 2.0 (46 MB, explicit non-answer) covers the need.
3. **τ-bench replaced by `sierra-research/tau2-bench`** (τ³): the original repository is
   officially deprecated. Consequence: the numbers from the 2024 τ-bench paper are
   not comparable to ours (75+ tasks fixed since).
4. **BIRD via Mini-Dev** (500 SELECT instances, 11 databases, PostgreSQL versions provided);
   the full dataset (33 GB) is excluded. The sqlglot SQLite→Postgres conversion remains a
   deliverable for Spider.
5. **DocVQA via the HF mirrors** (`lmms-lab/DocVQA` for val/test): the official site
   requires registration and had a broken TLS certificate on 2026-08-26. Evaluation
   on the validation split (test answers hidden everywhere).
6. **Licenses flagged, no redistribution**: ChartQA is GPL-3.0, FUNSD is
   non-commercial (images never redistributed), the original DocVQA license is unclear,
   and the CC labels of the BEIR repositories are the packaging's claim, not an
   upstream guarantee. No public data is versioned in the repository.
7. **Fragile paths documented**: MuSiQue (Google Drive), 2WikiMultihopQA (Dropbox),
   QASPER (`refs/convert/parquet` branch only), Spider (SQLite databases on Google
   Drive — plan a cached copy), HybridQA and WikiTableQuestions (HF repositories with
   dead scripts → go through GitHub). Each future loader will have to pin its provenance.

## Consequences

Contamination remains an accepted bias of all these datasets (Spider in particular): it is
an object of measurement in phase 2, not a reason for exclusion. The agentic harnesses
(tau2-bench, BFCL, AgentDojo) are not datasets and will be integrated as external runners
in phase 4 — BFCL requires Python 3.10, hence a separate uv environment.
