"""Ingestion pipeline: documents → chunks → embeddings → index (ADR 007).

Idempotent at two levels: a document whose fingerprint has not changed is not
rewritten, and a chunk that already has its vector in the index is not re-embedded. We
never pay twice for an embedding already computed — phase 3 will industrialize this idea
with an orchestrator, but the property is there right now.
"""

import time
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from llm_testbench.ingest.chunking import EmbeddingInput, RecursiveChunker
from llm_testbench.ingest.parsing import ParsedDocument
from llm_testbench.ingest.store import IndexSpec, PgVectorStore
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.embeddings import EmbeddingRequest
from llm_testbench.llm.governance import DataClass


class IngestReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    index_key: str
    documents_seen: int = 0
    documents_written: int = 0
    chunks_total: int = 0
    chunks_embedded: int = 0
    embedding_tokens: int = 0
    embedding_calls: int = 0
    cost_usd: float | None = None
    """Sum of the embedding costs; ``None`` as soon as one call has an unknown cost."""
    duration_ms: float = Field(ge=0)


class IngestionPipeline:
    def __init__(
        self,
        *,
        client: LLMClient,
        store: PgVectorStore,
        chunker: RecursiveChunker,
        data_class: DataClass,
        batch_size: int = 64,
    ) -> None:
        self._client = client
        self._store = store
        self._chunker = chunker
        self._data_class = data_class
        self._batch_size = batch_size

    def index_spec(
        self,
        *,
        index_key: str,
        source_key: str,
        embedding_model: str,
        dimensions: int,
        description: str = "",
    ) -> IndexSpec:
        """The index definition consistent with THIS chunker: this is what guarantees that
        the registry really describes what produced the chunks."""
        from llm_testbench.llm.types import ModelRef

        return IndexSpec(
            index_key=index_key,
            source_key=source_key,
            embedding_model=ModelRef.parse(embedding_model),
            dimensions=dimensions,
            chunker=self._chunker.describe(),
            description=description,
        )

    async def ingest(self, spec: IndexSpec, documents: Iterable[ParsedDocument]) -> IngestReport:
        if spec.chunker != self._chunker.describe():
            raise ValueError(
                "the pipeline chunker does not match the index chunker "
                f"({spec.chunker} ≠ {self._chunker.describe()})"
            )
        start = time.perf_counter()
        await self._store.register_index(spec)
        seen = written = chunks_total = embedded = tokens = calls = 0
        cost: float | None = 0.0
        pending: list[EmbeddingInput] = []

        async def flush() -> None:
            nonlocal embedded, tokens, calls, cost
            if not pending:
                return
            result = await self._client.embed(
                EmbeddingRequest(
                    model=spec.embedding_model,
                    texts=tuple(item.text for item in pending),
                    data_class=self._data_class,
                    dimensions=spec.dimensions,
                )
            )
            await self._store.add_embeddings(spec, list(zip(pending, result.vectors, strict=True)))
            embedded += len(pending)
            tokens += result.usage.input_tokens
            calls += 1
            cost = None if cost is None or result.cost_usd is None else cost + result.cost_usd
            pending.clear()

        # What is already there, read once: two queries for the whole source instead of
        # two per document. On an index that is up to date, the pass below touches the
        # database no more (5,000 documents: 3 seconds instead of 40).
        stored_documents = await self._store.document_checksums(spec.source_key)
        stored_vectors = await self._store.embedding_checksums(spec)

        for document in documents:
            seen += 1
            chunks = self._chunker.chunk(document)
            chunks_total += len(chunks)
            # What the model sees is the title + the chunk (BEIR convention), and that is
            # what the vector is keyed on: a retitled document is embedded again.
            inputs = [EmbeddingInput.from_chunk(document, chunk) for chunk in chunks]
            if stored_documents.get(document.doc_id) != document.checksum:
                # New or modified: its old chunks go away, and their vectors with them.
                await self._store.upsert_document(spec.source_key, document, chunks)
                written += 1
                pending.extend(inputs)
            else:
                pending.extend(
                    item
                    for item in inputs
                    if stored_vectors.get(item.chunk.chunk_id) != item.checksum
                )
            while len(pending) >= self._batch_size:
                batch, rest = pending[: self._batch_size], pending[self._batch_size :]
                pending[:] = batch
                await flush()
                pending.extend(rest)
        await flush()

        return IngestReport(
            index_key=spec.index_key,
            documents_seen=seen,
            documents_written=written,
            chunks_total=chunks_total,
            chunks_embedded=embedded,
            embedding_tokens=tokens,
            embedding_calls=calls,
            cost_usd=cost,
            duration_ms=(time.perf_counter() - start) * 1000.0,
        )
