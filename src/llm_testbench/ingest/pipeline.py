"""Pipeline d'ingestion : documents → chunks → embeddings → index (ADR 007).

Idempotent à deux niveaux : un document dont l'empreinte n'a pas changé n'est pas
réécrit, et un chunk qui a déjà son vecteur dans l'index n'est pas ré-embarqué. On ne
repaie jamais un embedding déjà calculé — la phase 3 industrialisera cette idée avec
un orchestrateur, mais la propriété est là dès maintenant.
"""

import time
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from llm_testbench.ingest.chunking import Chunk, RecursiveChunker
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
    """Somme des coûts d'embeddings ; ``None`` dès qu'un appel a un coût inconnu."""
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
        """La définition d'index cohérente avec CE chunker : c'est ce qui garantit que le
        registre décrit bien ce qui a produit les chunks."""
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
                "le chunker du pipeline ne correspond pas à celui de l'index "
                f"({spec.chunker} ≠ {self._chunker.describe()})"
            )
        start = time.perf_counter()
        await self._store.register_index(spec)
        seen = written = chunks_total = embedded = tokens = calls = 0
        cost: float | None = 0.0
        pending: list[Chunk] = []

        async def flush() -> None:
            nonlocal embedded, tokens, calls, cost
            if not pending:
                return
            result = await self._client.embed(
                EmbeddingRequest(
                    model=spec.embedding_model,
                    texts=tuple(c.text for c in pending),
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

        for document in documents:
            seen += 1
            chunks = self._chunker.chunk(document)
            chunks_total += len(chunks)
            if await self._store.upsert_document(spec.source_key, document, chunks):
                written += 1
            pending.extend(await self._store.missing_embeddings(spec, chunks))
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
