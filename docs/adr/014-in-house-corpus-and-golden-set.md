# ADR 014 — The in-house corpus and the golden set

- **Date**: 2026-11-05
- **Status**: accepted

## Context

Phase 2.5 asks for one corpus with three uses (contamination, the golden set, the poisoned
documents of phase 7), selected on two criteria only: published after the cutoffs of the
models used, and hard to parse. Phase 2.6 asks for a golden set of 50 to 80 questions with a
taxonomy, drafted with assistance, reviewed in full by a person through a CLI, versioned
with a changelog. The corpus was chosen on 2026-11-05: arXiv papers under CC BY 4.0. Six
decisions remained.

## Decisions

**1. "After the cutoff" is established from a release date, never from a cutoff.** A
training cutoff is what a provider says, when it says it. A release date is a fact: a model
cannot have read a text first published after it was available. `config/corpus.toml` lists
each model the testbench uses with a date on which it is known to have been available and
where that date comes from; the freshness floor must be after all of them or the file does
not load. The date compared is the one of a paper's **first** version (arXiv lists records
by last modification: a 2013 paper revised yesterday looks recent). The manifest carries
the floor and the models; `Manifest.fresh_for` answers false for a model it does not list.
A newer model voids the property, and the code says so instead of assuming. Limit: a paper
first submitted to arXiv on a given day may have circulated earlier elsewhere.

**2. The reference text is arXiv's own HTML rendering, not ours.** The golden set must be
written against a text that did not go through a PDF parser, so that the same questions
can judge a parser later. arXiv renders the LaTeX source of a paper to HTML (LaTeXML) with
sections, paragraphs, tables and footnotes as explicit elements; `eval/corpus/reference.py`
turns that page into sections (a table as rows with `|`, a footnote moved out of its
sentence, a formula as its LaTeX source, the bibliography left out). Rejected: converting
the LaTeX source ourselves, a parser project of its own, which is what the decision of
2026-11-05 ("the LaTeX source gives a reference text") would have meant taken literally.
A paper LaTeXML cannot render has no page and is not selected (16 of the 355 candidates
examined).

**3. One naive extractor, on purpose.** `ingest/pdf.py` asks `pypdf` for the text of each
page and takes what comes: one section per page, no columns, no tables, no footnotes
handled. It is the baseline phase 3 has to beat, and what the system as built indexes.

**4. The selection is a rule, and its result is a file.** Candidates: CC BY 4.0, first
submitted on or after the floor, primary category in a list that only bounds the harvest.
Difficulty is counted on the reference text: tables + footnotes + displayed formulas at
least 12, at least 3 tables, 20,000 to 120,000 characters; the first 200 in the order of
their identifiers. Thresholds were set on the first 24 candidates: footnotes are rare
(a third of the papers kept have one), tables are everywhere, so a footnote counts and is
not required. The documents stay in `data/cache/`; the manifest
(`data/corpus/arxiv-fresh/manifest.json`: identifiers, authors, licenses, hashes, features)
is versioned. Selecting again later does not give the same papers; downloading from the
manifest does (`make corpus-download`). The hash of the reference text is taken on the
parsed text, not on the page: arXiv's header and footer change without the paper changing.

**5. A model drafts, code checks what code can check, a person decides.** The drafter
(`openai/gpt-5.6-terra`, not the generator under test) reads the beginning of one paper and
writes one question per requested kind, the kinds asked in rotation: factual, multi-hop,
unanswerable, ambiguous, trap, temporal. Then three checks that need no person:
every quoted sentence is looked up in the reference text, word for word; every draft is
asked to the generator with no document, and a right answer marks the question as
guessable; every draft marked unanswerable is reread against the **whole** paper by a
cheaper model, which must quote the passage if it claims the answer is there, and that
quote is looked up too. None of these accepts or rejects anything: they are shown to the
reviewer (`make golden-review`), who accepts, edits or rejects each draft. One rule is
enforced: a question that has an answer cannot be accepted without a quote found in the
document, because nothing would tell the harness where the answer is.

**6. Three files and a changelog.** `drafts.jsonl` (what the model proposed),
`reviews.jsonl` (the reviewer's decisions, appended, the last one wins), `questions.jsonl`
(the frozen set an evaluation reads, rebuilt by `make golden-freeze`), `CHANGELOG.md` (one
entry per version: counts per kind, added, removed, changed). A question keeps its
identifier across versions. A score on the golden set is comparable only with a score on
the same version of it.

## Consequences

- 200 documents, first submitted on 2026-10-20 and 2026-10-21, 1.1 GB of PDFs in the local
  cache, a manifest of 150 KB in the repository. Median document: 64,000 characters,
  9 tables, 11 displayed formulas.
- 83 drafts on 30 documents ($0.57): 15 of each kind except temporal (8: most papers state
  no dates). All 106 quotes were found word for word. The generator, asked without any
  document, gave the reference answer on 2 drafts and said it did not know on 78: the
  questions are not guessable, where 53% of HotpotQA's are answered from memory. 3 of the
  15 drafts marked unanswerable are answered deeper in their paper, according to the
  second reading.
- The quotes versioned with the drafts are excerpts of CC BY 4.0 papers; the manifest names
  the authors and the license of each, and `data/golden/inhouse/README.md` says so.
- The golden set cannot be measured before the review. Its arms (naive text against
  reference text, which is what parsing costs) are wired after the first freeze.
- "Unanswerable" is the kind code can check least: the second reading is a model too. A
  wrong unanswerable question punishes a system for being right.
- All papers are computer science, most of them machine learning: the corpus says nothing
  about scanned documents, forms or spreadsheets. It was chosen for formats that break a
  PDF extraction and for a reference text to measure it against, not for coverage.
