"""``DocumentSource`` : la source documentaire sur pgvector (ADR 007).

La seule implémentation de :class:`Source` en phase 1. Une recherche = un embedding de
la question (gouverné, facturé, tracé comme tout appel) puis une recherche cosinus dans
l'index. Chaque résultat porte une provenance complète : le lecteur peut ouvrir le
document, la section et la plage de caractères cités, et vérifier l'empreinte.
"""

from llm_testbench.ingest.store import IndexSpec, PgVectorStore
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.embeddings import EmbeddingRequest
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
        embedding = await self._client.embed(
            EmbeddingRequest(
                model=self.spec.embedding_model,
                texts=(query.text,),
                data_class=query.data_class,
                dimensions=self.spec.dimensions,
            )
        )
        hits = await self._store.search(
            self.spec, embedding.vectors[0], k=query.k, filters=query.filters or None
        )
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
                locator="document entier",
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
