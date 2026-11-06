# Sources, evidence, citations

What the chat service searches, what a search returns, and how a returned excerpt becomes a
citation the reader can check. The vocabulary is the same for documents today and for SQL,
APIs and images in phase 4.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eef2f8", "primaryTextColor": "#1b1f24", "primaryBorderColor": "#5b6b82", "lineColor": "#7d8590", "textColor": "#1b1f24", "edgeLabelBackground": "#eef2f8", "noteBkgColor": "#fff4ce", "noteTextColor": "#1b1f24", "noteBorderColor": "#c9a227", "classText": "#1b1f24", "clusterBkg": "#f6f8fa", "clusterBorder": "#8b949e", "fontSize": "14px"}}}%%
classDiagram
  direction LR
  class Source {
    <<Protocol>>
    +key : str
    +kind : SourceKind
    +capabilities : frozenset~Capability~
    +search(query) list~Evidence~
    +fetch(document_id) Evidence | None
    +describe() SourceInfo
  }
  class DocumentSource {
    +key : str
    +kind : SourceKind
    +capabilities : frozenset~Capability~
    +spec : IndexSpec
    +search(query) list~Evidence~
    +fetch(document_id) Evidence | None
    +describe() SourceInfo
  }
  class SourceKind {
    <<enumeration>>
    DOCUMENTS
    SQL
    API
    STRUCTURED
    IMAGES
  }
  class Capability {
    <<enumeration>>
    SEARCH
    FETCH
    FILTER
    QUERY
    CALL
  }
  class SearchQuery {
    +text : str
    +k : int
    +filters : dict~str, str~
    +data_class : DataClass
  }
  class Evidence {
    +text : str
    +score : float
    +rank : int
    +provenance : Provenance
    +metadata : dict~str, str~
  }
  class Provenance {
    +source_key : str
    +document_id : str
    +chunk_id : str | None
    +locator : str
    +title : str | None
    +uri : str | None
    +checksum : str | None
    +ingested_at : datetime | None
    +label() str
  }
  class Citation {
    +index : int
    +label : str
    +provenance : Provenance
    +from_evidence(index, evidence) Citation$
    +render() str
  }
  class SourceInfo {
    +key : str
    +kind : SourceKind
    +capabilities : frozenset~Capability~
    +description : str
    +document_count : int | None
  }
  class PgVectorStore
  class LLMClient
  DocumentSource ..|> Source : satisfies, the only source of phase 1
  DocumentSource --> LLMClient : embed() the question, governed and billed
  DocumentSource --> PgVectorStore : search(), fetch_document(), counts()
  Source --> SourceKind : kind
  Source --> Capability : capabilities, what this source can do
  Source ..> SearchQuery : search() takes
  Source ..> Evidence : search() returns, ranked from 1
  Source ..> SourceInfo : describe() returns, served by GET /sources
  Evidence *-- Provenance : provenance, always complete
  Citation --> Provenance : provenance, copied from the evidence
  Evidence ..> Citation : from_evidence(index, evidence)
```

## How to read it

- `Source` is a protocol with three verbs. The chat service depends on it, never on
  `DocumentSource`; a SQL source in phase 4 is a new class with the same three methods and
  the capabilities `QUERY` instead of `SEARCH`.
- A search is itself a model call: the question is embedded through `LLMClient`, with the
  `data_class` of the `SearchQuery`, so governance applies to the question before it applies
  to the answer.
- `Evidence` is a ranked excerpt with a complete `Provenance`: source, document, chunk,
  locator (section and character range), fingerprint, ingestion time. The reader can open the
  cited passage and check it has not changed.
- A `Citation` is an `Evidence` the model actually cited, by its number in the prompt.
  `label` is the human-readable form, `render` the line shown under an answer.
- `fetch` returns a whole document as one `Evidence` with the locator "whole document": the
  same type serves a passage and a full text.

## In the code

[sources/types.py](../../src/llm_testbench/sources/types.py),
[sources/documents.py](../../src/llm_testbench/sources/documents.py).

## In the notebooks

Notebook 02, part 4.1.
