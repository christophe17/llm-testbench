# PHASE 3 — Advanced RAG (weeks 7–8)

**Each technique is behind a flag and measured on the public datasets.** Non-significant gain
→ we remove it and document why. A technique removed with quantified evidence is worth more
than ten stacked techniques.

Order of observed payoff:

1. hybrid BM25 + dense search with RRF fusion;
2. cross-encoder re-ranking;
3. comparison of 4 chunking strategies (recursive, semantic, parent-document, late
   chunking) on **raw documents** with QASPER — and PDF parsing, postponed from phase 1 and
   measured here;
4. contextual retrieval;
5. query transformation (HyDE, multi-query, multi-hop decomposition, routing);
6. metadata filtering;
7. **GraphRAG** (extracting an entity graph from the corpus, graph-based retrieval) — last:
   high indexing cost for uncertain gains in the literature; it is the most serious
   candidate for a quantified removal, and that is just fine.

## The operated ingestion pipeline — named deliverable

It is what answers the word "pipeline" in AI Engineer job postings; "going fast on it" means
not getting lost in it, not botching it.

Ingestion becomes an orchestrated pipeline. Its reason to exist is not the freshness of the
corpus, which is static on the public datasets, but the **experiment matrix**: each combination
of dataset × chunking strategy × embedding model × retrieval parameters produces a distinct
index, and there will be more than a hundred of them between phases 2 and 3.

What you build: jobs parameterized and partitioned on these dimensions, idempotency, caching
of the expensive steps (embeddings cost money), rerunning only what changed, resuming
after failure, **lineage** linking each number in the results table to the index and the code
that produced it, and **input data validation with Pandera** (schema of the benchmark files,
encoding, duplicates, missing fields).

Three obligations:

- an **orchestrator ADR**: Dagster vs Airflow vs Prefect;
- a row in the master table "**regenerating a row from scratch**: duration, cost, share
  served by the cache";
- notebook (5) below, entirely devoted to the pipeline.

**Acceptance criterion**: I must be able to regenerate any row of the master table
from scratch, with a single command. That is what separates "I built a RAG" from "I
operated a RAG".

**On the small in-house corpus of phase 2**, also demonstrate the living case: adding,
updating and deleting documents, change detection, incremental reindexing without rebuilding
everything.

## Deliverables

**Key deliverable**: table "technique → quality gain with confidence interval → p95
latency cost → € cost", plus the gap to the literature.

**Notebooks**: (1) why hybrid search saves acronyms and jargon; (2) the showdown of the
chunking strategies on raw documents; (3) query transformation: when it helps,
when it costs for nothing; (4) our pipeline against **LlamaIndex** out of the box **and against
Bedrock Knowledge Bases** (AWS's managed RAG: ingestion from S3, chunking, retrieval and
generation in a few clicks, on the cheapest vector store available, created and destroyed
within the day) on the same BEIR dataset — where the framework or the managed service saves
time, where it plateaus, quantified (ours first, then the comparison; both ports live
in the benchmark material, not in `src/` — AWS services entry rule, `CLAUDE.md`
§4); (5) the
experiment matrix: regenerating a hundred indexes without recomputing everything — partitions,
cache rate, backfill, resume after failure and lineage visible in the output.
