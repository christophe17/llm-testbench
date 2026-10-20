# ADR 004 — Loading interface for evaluation datasets

- **Date**: 2026-08-26
- **Status**: accepted

## Context

A dozen public datasets will join the testbench over the phases, each with its own format
(HF Parquet across 2-3 repositories, zips, GitHub JSON) and its own traps (int-typed ids,
unjudged queries, gated splits). Phase 0 freezes the contract with ONE reference loader (SciFact).

## Options considered

1. **Reuse an existing framework** (`ir_datasets`, `beir` package) — covers retrieval,
   but not the following families (QA, SQL, images), imposes its types, and hides
   precisely the mechanics the project wants to expose.
2. **In-house validated types + per-family loaders** — more code of our own, but a
   single extensible contract and explicit integrity validation.

## Decision

Option 2. A loader produces a **frozen** Pydantic `RetrievalDataset` that validates at
construction: unique ids, qrels with no orphan reference, no query without a
judgment (out-of-split queries are filtered out by the loader — SciFact has 1,109 queries for
300 judged in test). The join is a pure function (`build_retrieval_dataset`),
identical for real data and test fixtures. Provenance (`DatasetInfo`:
source, license as displayed, homepage) travels with the data, and so does the `sampled` flag:
a number computed on a truncated dataset declares itself unpublishable.

The following families (QA, SQL…) will have their own output types but the same
contract: declared provenance, validated integrity, explicit sample mode.

## Consequences

Adding a BEIR dataset = an entry in `BEIR_DATASETS` + fixtures + tests. The phase 2
harness will consume these types as is. Accepted limit: sample mode keeps
only the judged documents (no more distractors) — enough to check the
mechanics, meaningless for a score, and it says so on the label.
