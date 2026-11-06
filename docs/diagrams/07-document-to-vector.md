# From document to vector

The ingestion path of notebook 02: a parsed document is cut into chunks, each chunk is
embedded with its title, and the vectors land in one Postgres table per index.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#eef2f8", "primaryTextColor": "#1b1f24", "primaryBorderColor": "#5b6b82", "lineColor": "#7d8590", "textColor": "#1b1f24", "edgeLabelBackground": "#eef2f8", "noteBkgColor": "#fff4ce", "noteTextColor": "#1b1f24", "noteBorderColor": "#c9a227", "classText": "#1b1f24", "clusterBkg": "#f6f8fa", "clusterBorder": "#8b949e", "fontSize": "14px"}}}%%
classDiagram
  direction LR
  class ParsedDocument {
    +doc_id : str
    +title : str
    +sections : tuple~Section~
    +source_uri : str | None
    +metadata : dict~str, str~
    +text : str
    +checksum : str
    +char_count : int
  }
  class Section {
    +title : str
    +text : str
    +order : int
  }
  class RecursiveChunker {
    +chunk_size : int
    +chunk_overlap : int
    +separators : tuple~str~
    +chunk(document) list~Chunk~
    +split_text(text) list~str~
    +describe() dict
  }
  class Chunk {
    +chunk_id : str
    +doc_id : str
    +ordinal : int
    +text : str
    +section_title : str
    +start_char : int
    +end_char : int
    +checksum : str
    +token_estimate : int
    +locator() str
  }
  class EmbeddingInput {
    +chunk : Chunk
    +text : str
    +checksum : str
    +from_chunk(document, chunk) EmbeddingInput$
  }
  class IndexSpec {
    +index_key : str
    +source_key : str
    +embedding_model : ModelRef
    +dimensions : int
    +chunker : dict
    +table : str
  }
  class IngestionPipeline {
    +index_spec(index_key, source_key, embedding_model, dimensions) IndexSpec
    +ingest(spec, documents) IngestReport
  }
  class IngestReport {
    +documents_seen : int
    +documents_written : int
    +chunks_total : int
    +chunks_embedded : int
    +embedding_tokens : int
    +embedding_calls : int
    +cost_usd : float | None
    +duration_ms : float
  }
  class PgVectorStore {
    +from_url(url) PgVectorStore$
    +ensure_schema()
    +register_index(spec)
    +upsert_document(source_key, document, chunks) bool
    +missing_embeddings(spec, inputs) list~EmbeddingInput~
    +add_embeddings(spec, rows)
    +search(spec, vector) list~SearchHit~
    +fetch_document(source_key, doc_id) StoredDocument | None
  }
  class StoredDocument {
    +source_key : str
    +doc_id : str
    +title : str
    +checksum : str
    +ingested_at : datetime
    +chunks : tuple~Chunk~
  }
  class SearchHit {
    +chunk : Chunk
    +score : float
    +document_title : str
    +document_uri : str | None
    +ingested_at : datetime
  }
  class LLMClient {
    +embed(request) EmbeddingResult
  }
  ParsedDocument *-- Section : sections, in order
  RecursiveChunker ..> Chunk : chunk(document) returns, with offsets
  Chunk ..> EmbeddingInput : from_chunk(), title plus text is what gets embedded
  IngestionPipeline --> RecursiveChunker : chunker
  IngestionPipeline --> PgVectorStore : store
  IngestionPipeline --> LLMClient : embed() in batches, governed and billed
  IngestionPipeline ..> IndexSpec : index_spec() stamps the chunker settings
  IngestionPipeline ..> IngestReport : ingest() returns
  PgVectorStore ..> StoredDocument : fetch_document()
  PgVectorStore ..> SearchHit : search(), cosine on the HNSW index
  StoredDocument *-- Chunk : chunks
  SearchHit --> Chunk : chunk
```

## How to read it

- Three fingerprints. `ParsedDocument.checksum` decides whether a document is rewritten;
  `Chunk.checksum` identifies a chunk's text; `EmbeddingInput.checksum` covers title plus
  text, which is what the model sees. A retitled document is embedded again, an unchanged one
  costs nothing: this is the idempotence of `ingest`.
- `IndexSpec` is the contract of an index: which source, which embedding model, how many
  dimensions, and the exact chunker settings. `ingest` refuses a spec whose chunker does not
  match the pipeline's, so the registry always describes what produced the vectors.
- One vector table per index (`IndexSpec.table`), one HNSW index per table. Two indexes of
  the same corpus with different chunkers coexist, which phase 3 needs for its matrix.
- Embeddings go through `LLMClient`, so the data class, the budget and the cost apply to
  indexing the same way they apply to a chat call. The report carries the cost.
- `SearchHit` is what the store returns; [08 sources, evidence, citations](08-sources-evidence-citations.md)
  turns it into `Evidence` with a provenance.

## In the code

[ingest/parsing.py](../../src/llm_testbench/ingest/parsing.py),
[ingest/chunking.py](../../src/llm_testbench/ingest/chunking.py),
[ingest/pipeline.py](../../src/llm_testbench/ingest/pipeline.py),
[ingest/store.py](../../src/llm_testbench/ingest/store.py), the schema in
[ingest/sql/](../../src/llm_testbench/ingest/sql/).

## In the notebooks

Notebook 02, parts 3.1 to 3.5.
