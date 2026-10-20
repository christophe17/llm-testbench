# ADR 007 — `Source` interface, ingestion and vector storage

- **Date**: 2026-09-03
- **Status**: accepted

## Context

The brief (phase 1) imposes a generic `Source` interface right now — declared
capabilities, uniform provenance, homogeneous citation whatever the origin — so that
phase 4 (SQL, API, structured data, images) is a plug-in and not a refactor. It
also imposes an ingestion "parsing → naive chunking → embeddings → pgvector index" with
traceability metadata, and a `/chat` with mandatory citations and explicit refusal. Phase
3 will produce **more than a hundred indexes** (dataset × chunking × embeddings × parameters)
on this same storage.

## Options considered

**Vector storage.**

1. **A single embeddings table** with a `vector` column of unfixed dimension.
   Simple, but pgvector only indexes (HNSW) a column of fixed dimension: as soon as we
   compare two embedding models of different dimensions, no more index.
2. **One index = one table** `emb_<key>` of fixed dimension, created by the code, plus a
   registry table that describes each index (dataset, chunker and its parameters, embedding
   model, dimension, date). **Selected**: it is exactly the experiment matrix
   of phase 3, and the *lineage* of each number starts here.
3. A dedicated vector service (Qdrant, Weaviate). Refused by the brief: Postgres + pgvector.

**Shape of the `/chat` response.**

1. **Structured output** (`{answer, citations, refused}`): clean, measurable, but
   incompatible with token streaming (half a JSON cannot be read).
2. **Text with `[n]` markers and a refusal sentinel sentence**, parsed afterwards, for
   both transports (JSON and SSE). **Selected**: one prompt, one parser, two
   transports; the refusal stays explicit and measurable (correct/unwarranted refusal rate in
   phase 2). The structured outputs of ADR 006 serve extraction (phase 4), not the
   chat.

**Chunking.** Recursive splitting by separators (paragraph → line → sentence → word), in
characters, with overlap. Deliberately naive: it is the baseline phase 3
must beat. Reimplemented (~60 lines) rather than imported: the notebook must be able to
read it in full.

## Decision

- **Types** (`sources/types.py`): `Provenance` (source key, document identifier,
  chunk identifier, human-readable locator, title, URI, text hash, ingestion
  date), `Evidence` (text, score, rank, provenance), `Citation` (number, homogeneous
  label `[n] source › document › locator`, provenance), `SearchQuery` (text, k,
  filters, **data class** — the question's embedding goes out too).
- **`Source` protocol**: `key`, `kind`, `capabilities` (declared set: search,
  fetch by identifier, filtering… extended in phase 4 by SQL, API), `search()`,
  `fetch()`. A single implementation in phase 1: `DocumentSource` on pgvector.
- **Ingestion** (`ingest/`): `ParsedDocument` in sections (text, markdown, and the
  QASPER full text already sectioned — no PDF in phase 1, phase 3 ADR); `Chunk` with
  deterministic identifier, hash and position; `RecursiveChunker`; pipeline that
  embeds in batches via `LLMClient.embed` (governance and cost included) and writes to
  Postgres; idempotence by chunk hash and by index.
- **Postgres schema** (`ingest/sql/`): `documents`, `chunks`, `indexes` (registry), and one
  `emb_<key>` table per index with `vector(dim)` and a cosine HNSW index. Idempotent
  creation at startup.
- **Search**: pgvector cosine distance (`<=>`), score = 1 − distance, bounded `k`.
- **Response**: versioned prompt `chat_answer` (mandatory `[n]` citations, exact refusal
  sentinel), parser shared by both transports.

## Consequences

Each row of the future master table will be able to cite its index key, hence its chunker, its
model and its date. The cost: one table per index (dozens, then hundreds),
which is the price of an honest experiment matrix and which Postgres handles with ease.
Storage tests require a database; they are marked `db` and skipped without
`LLM_TESTBENCH_DATABASE_URL` (offline CI unchanged), run locally on k3d.
