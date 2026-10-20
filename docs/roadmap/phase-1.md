# PHASE 1 — Production skeleton (weeks 2–3)

**Status: built** (merged into `main` on 2026-10-16); what remains are Christophe's
actions listed in `STATE.md` (keys, full runs, AWS bootstrap).

Quality is not yet the topic: we build the structure that we will measure afterwards.

**LLM layer**: provider abstraction, structured outputs with validation and repair,
timeouts, retry/backoff, circuit breaker, token budget, exact and semantic cache,
cancellable SSE streaming. **Data governance** from this phase on, as a property of the
layer: data class carried by every request, backend registry with metadata
(entity, region, retention, training, subprocessors), deny-by-default policy,
decision traced in the audit, also applied to embeddings and the judge. The actual
constraints are not known yet: an initial permissive policy on public data, to be
tightened when they become clearer (ADR 006).

**Source abstraction right now.** The system will eventually query documents, a
SQL database, APIs, structured data and images (phase 4). Generic `Source` interface
— declared capabilities, metadata, uniform provenance, consistent citation whatever
the origin — and first the document connector. Phase 4 becomes a plug-in
instead of a refactor (ADR 007).

**Ingestion**: careful parsing (parsing makes half of a RAG's quality), deliberately naive
recursive chunking as a baseline to beat, traceability metadata, measured
comparison of at least 3 embedding models via MTEB.

**API**: `/chat` with mandatory citations and explicit refusal when the context does not
allow an answer. Deployed on the cluster, not only locally.

**Infra**: Langfuse (postponed from phase 0, ADR 002) and AWS modules. Each building block
explained in a `docs/infra/` guide.

**Notebooks**: (1) anatomy of a robust LLM call — what breaks in prod and how we
absorb it; (2) from document to indexed chunk, with all the intermediate outputs visible.

## Plan decisions (2026-09-03)

- Providers: native Anthropic (+ Bedrock) and OpenAI-compatible; default generator
  `anthropic/claude-sonnet-5`; OpenAI as second provider and phase 2 judge (ADR 006).
- Long documents: QASPER (full text already structured, CC BY 4.0); PDF parsing postponed to
  phase 3, where it will be measured.
- Embeddings compared via `mteb` on SciFact: OpenAI text-embedding-3-small,
  BAAI/bge-base-en-v1.5 (local), all-MiniLM-L6-v2 ("tutorial" control). The nDCG@10 values
  obtained are a benchmark that the phase 2 harness will have to reproduce.
- Langfuse via Helm on k3d (Docker VM with 12 GB).
- Manual cloud deployment through `make`, no OIDC pipeline. *Superseded on 2026-10-19 (ADR
  009): `make deploy`, plus the same deployment by GitHub Actions with an OIDC role, triggered
  manually.*
- psycopg 3 with raw SQL, HNSW index.
