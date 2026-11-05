"""``DocumentSource``: the document source on pgvector (ADR 007).

The only implementation of :class:`Source` in phase 1. A search = an embedding of the
question (governed, billed, traced like any call) then a cosine search in the index.
Each result carries a complete provenance: the reader can open the cited document,
section and character range, and check the fingerprint.
"""

from collections.abc import Sequence

from llm_testbench.ingest.store import IndexSpec, PgVectorStore
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.embeddings import EmbeddingRequest, EmbeddingResult
from llm_testbench.llm.governance import DataClass
from llm_testbench.sources.types import (
    Capability,
    Evidence,
    Provenance,
    SearchQuery,
    SourceInfo,
    SourceKind,
)


class DocumentSource:
    kind = SourceKind.DOCUMENTS
    capabilities = frozenset({Capability.SEARCH, Capability.FETCH, Capability.FILTER})

    def __init__(self, *, client: LLMClient, store: PgVectorStore, spec: IndexSpec) -> None:
        self.key = spec.source_key
        self.spec = spec
        self._client = client
        self._store = store

    async def search(self, query: SearchQuery) -> list[Evidence]:
        embedding = await self.embed_query(query.text, query.data_class)
        return await self.search_vector(embedding.vectors[0], k=query.k, filters=query.filters)

    async def embed_query(self, text: str, data_class: DataClass) -> EmbeddingResult:
        """The question as a vector, by the model that embedded the chunks. Apart from
        :meth:`search_vector` so that a caller who accounts for the call (the evaluation
        harness) gets its cost and its duration, not only its result."""
        return await self._client.embed(
            EmbeddingRequest(
                model=self.spec.embedding_model,
                texts=(text,),
                data_class=data_class,
                dimensions=self.spec.dimensions,
                input_type="query",
            )
        )

    async def search_vector(
        self, vector: Sequence[float], *, k: int, filters: dict[str, str] | None = None
    ) -> list[Evidence]:
        hits = await self._store.search(self.spec, vector, k=k, filters=filters or None)
        return [
            Evidence(
                text=hit.chunk.text,
                score=hit.score,
                rank=rank,
                provenance=Provenance(
                    source_key=self.key,
                    document_id=hit.chunk.doc_id,
                    chunk_id=hit.chunk.chunk_id,
                    locator=hit.chunk.locator(),
                    title=hit.document_title or None,
                    uri=hit.document_uri,
                    checksum=hit.chunk.checksum,
                    ingested_at=hit.ingested_at,
                    extra={"index_key": self.spec.index_key},
                ),
                metadata=dict(hit.document_metadata),
            )
            for rank, hit in enumerate(hits, start=1)
        ]

    async def fetch(self, document_id: str) -> Evidence | None:
        stored = await self._store.fetch_document(self.key, document_id)
        if stored is None:
            return None
        return Evidence(
            text="\n\n".join(chunk.text for chunk in stored.chunks),
            score=1.0,
            rank=1,
            provenance=Provenance(
                source_key=self.key,
                document_id=document_id,
                locator="whole document",
                title=stored.title or None,
                uri=stored.uri,
                checksum=stored.checksum,
                ingested_at=stored.ingested_at,
            ),
            metadata=dict(stored.metadata),
        )

    async def describe(self) -> SourceInfo:
        documents, _ = await self._store.counts(self.key)
        return SourceInfo(
            key=self.key,
            kind=self.kind,
            capabilities=self.capabilities,
            description=f"index {self.spec.index_key} ({self.spec.embedding_model})",
            document_count=documents,
        )
