# The in-house corpus and the golden set

A corpus selected by rule and recorded in a manifest; questions that go from a model's
draft to a person's decision to a frozen version.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eef2f8", "primaryTextColor": "#1b1f24", "primaryBorderColor": "#5b6b82", "lineColor": "#7d8590", "textColor": "#1b1f24", "edgeLabelBackground": "#eef2f8", "noteBkgColor": "#fff4ce", "noteTextColor": "#1b1f24", "noteBorderColor": "#c9a227", "classText": "#1b1f24", "clusterBkg": "#f6f8fa", "clusterBorder": "#8b949e", "fontSize": "14px"}}}%%
classDiagram
  direction LR
  class ArxivClient {
    +harvest(set_spec, since, until) Iterator~ArxivRecord~
    +html(arxiv_id, version) str
    +pdf(arxiv_id, version) bytes
  }
  class ArxivRecord {
    +arxiv_id : str
    +license : str
    +submitted : datetime
    +categories : tuple~str~
    +primary_category : str
  }
  class CorpusConfig {
    +freshness_floor : date
    +models : dict, name to ModelFreshness
    +license : str
    +size : int
    +min_difficulty : int
    +golden : GoldenConfig
  }
  class Manifest {
    +freshness_floor : date
    +models : dict, name to ModelFreshness
    +selection : dict
    +documents : tuple~ManifestEntry~
    +fresh_for(model) bool
    +entry(doc_id) ManifestEntry
  }
  class ManifestEntry {
    +arxiv_id : str
    +authors : str
    +license : str
    +submitted : datetime
    +reference_sha256 : str
    +pdf_sha256 : str
    +features : ReferenceFeatures
    +doc_id : str
  }
  class ReferenceFeatures {
    +characters : int
    +tables : int
    +footnotes : int
    +formulas : int
    +difficulty : int
  }
  class Corpus {
    +manifest : Manifest
    +reference(entry) ParsedDocument
    +extracted(entry) ParsedDocument
    +pdf_path(entry) Path
    +missing() list~str~
  }
  class Drafter {
    +model : ModelRef
    +draft(document, categories) list~Draft~
  }
  class Draft {
    +draft_id : str
    +category : Category
    +question : str
    +answer : str
    +quotes : tuple~Quote~
    +closed_book_correct : bool
    +found_elsewhere : Quote
    +problems() list~str~
  }
  class Quote {
    +doc_id : str
    +text : str
    +section : str
    +found : bool
  }
  class Review {
    +draft_id : str
    +decision : accepted, edited or rejected
    +question : str
    +answer : str
    +category : Category
  }
  class GoldenQuestion {
    +question_id : str
    +category : Category
    +question : str
    +answer : str
    +answerable : bool
    +quotes : tuple~Quote~
    +edited : bool
  }
  ArxivClient ..> ArxivRecord : harvest() yields
  CorpusConfig ..> Manifest : build_corpus() applies the selection
  Manifest *-- ManifestEntry : documents
  ManifestEntry --> ReferenceFeatures : features, what makes it hard to parse
  Corpus --> Manifest : manifest, and the files it vouches for
  Drafter ..> Draft : draft() returns, quotes looked up
  Draft *-- Quote : quotes, found or not in the reference text
  Review ..> Draft : a person's decision on one draft
  Draft ..> GoldenQuestion : apply_review() with an accepting review
  GoldenQuestion *-- Quote : quotes, the gold passages
```

## How to read it

- **Freshness is a property of the manifest**: a floor, and the models it is known to hold
  for. `fresh_for` answers false for a model that is not listed.
- **`Corpus` gives two texts of a document**: `reference` (from arXiv's HTML rendering,
  what a perfect parser would produce) and `extracted` (what `ingest/pdf.py` gets out of
  the PDF). Both are checked against the hashes of the manifest.
- **A quote is evidence only when `found`**: `locate` (`eval/golden/drafting.py`) looks
  it up in the reference text, word for word. `closed_book_correct` and
  `found_elsewhere` are the two automatic checks; `problems()` is what the reviewer is
  shown.
- **Three states, three files** (`eval/golden/store.py`): drafts, reviews (appended, the
  last one wins), and the frozen questions written by `freeze` with a changelog entry.

Code: `src/llm_testbench/eval/corpus/`, `eval/golden/`, `ingest/pdf.py`. Notebook:
phase 2, notebook 4; notebook 3 for the freshness rule.
