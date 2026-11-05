# The in-house golden set

Questions written for the in-house corpus (`data/corpus/arxiv-fresh/manifest.json`), to
measure the system on documents no model has read. How it is built: ADR 014 and
notebook 4 of phase 2.

| File | Content | Written by |
|---|---|---|
| `drafts.jsonl` | what a model proposed: one question per line, its kind, reference answer, quoted evidence, and what the automatic checks found | `make golden-draft`, `make golden-probe` |
| `reviews.jsonl` | a person's decision on each draft (accepted, edited, rejected); appended, the last line for a draft wins | `make golden-review` |
| `questions.jsonl` | the frozen set an evaluation reads | `make golden-freeze VERSION=v1 SUMMARY="..."` |
| `CHANGELOG.md` | one entry per frozen version | `make golden-freeze` |

A draft is never used for a measurement. `make golden-status` says where the set stands.

**Attribution.** The quotes in these files are excerpts of the papers listed in the
manifest, each published on arXiv under the Creative Commons Attribution 4.0 license
(https://creativecommons.org/licenses/by/4.0/). The manifest gives, for every paper, its
title, its authors and its arXiv identifier. Quotes are verbatim, whitespace aside; formulas
appear as their LaTeX source.
