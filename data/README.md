# data/

- `cache/` — local cache of the downloaded public datasets (Hugging Face, zips…). **Never
  versioned** (`.gitignore`): everything is re-downloaded by the loaders in
  `src/llm_testbench/eval/loaders/`, which are the single source of truth on provenance.
- The in-house golden set (phase 2) will live here, **versioned**, with its CHANGELOG.

Never commit redistributed public data: some licenses forbid it (details in
`docs/datasets-verification-2026-08-26.md`). The only data versioned in the repository is
the tiny hand-written fixtures in `tests/fixtures/`.
