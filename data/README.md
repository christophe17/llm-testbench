# data/

- `cache/` — local cache of the downloaded public datasets (Hugging Face, zips…). **Never
  versioned** (`.gitignore`): everything is re-downloaded by the loaders in
  `src/llm_testbench/eval/loaders/`, which are the single source of truth on provenance.
- `corpus/arxiv-fresh/manifest.json` — the in-house corpus (phase 2.5), **versioned as a
  manifest only**: identifiers, authors, licenses, hashes and the date after which every
  document was first published. The documents themselves are downloaded into `cache/` by
  `make corpus-download` (1.1 GB).
- `golden/` — what people wrote or decided, **versioned**: `judge_calibration/` (the 50
  items and their hand labels), `inhouse/` (the golden set: drafts, reviews, frozen
  questions, CHANGELOG; see its README).
- `results/` — the measured numbers, **versioned**: `runs/<suite>/<arm>.json` is the latest
  full run of each arm of the harness (metrics with intervals, per-query scores, document
  ids, never a text), `gate/baseline.json` the sample-mode scores the regression gate
  compares with; the other files are the `mteb` runs of phase 1.

Never commit redistributed public data: some licenses forbid it (details in
`docs/datasets-verification-2026-08-26.md`). The only data versioned in the repository is
the tiny hand-written fixtures in `tests/fixtures/`.
