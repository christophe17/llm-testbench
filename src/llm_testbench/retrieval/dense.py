"""Dense retrieval on a pgvector index, answered at the document level.

The question is embedded by the model that embedded the chunks (through ``LLMClient``:
governed, priced, traced), the nearest chunks are found, and each document is ranked by its
best chunk. The same index can be read two ways, and the difference is a number the harness
reports rather than an assumption:

- ``exact``: every vector is compared, the index is not used. The reference;
- ``hnsw``: the approximate index, the path the API serves, with pgvector's settings.
"""

import time
from typing import Literal

from llm_testbench.ingest.store import IndexSpec, PgVectorStore
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.embeddings import EmbeddingRequest
from llm_testbench.llm.governance import DataClass
from llm_testbench.retrieval.types import Description, Retrieval, RetrievedDocument

SearchMode = Literal["exact", "hnsw"]


class DenseRetriever:
    def __init__(
        self,
        *,
        client: LLMClient,
        store: PgVectorStore,
        spec: IndexSpec,
        search: SearchMode = "hnsw",
        ef_search: int | None = None,
        candidates: int | None = None,
        data_class: DataClass = DataClass.PUBLIC,
    ) -> None:
        self._client = client
        self._store = store
        self._spec = spec
        self._search: SearchMode = search
        self._ef_search = ef_search
        self._candidates = candidates
        self._data_class = data_class

    def describe(self) -> Description:
        description: Description = {
            "retriever": "dense",
            "index_key": self._spec.index_key,
            "embedding_model": str(self._spec.embedding_model),
            "dimensions": self._spec.dimensions,
            "search": self._search,
            "aggregation": "best chunk per document",
        }
        description.update({f"chunker.{key}": value for key, value in self._spec.chunker.items()})
        if self._search == "hnsw":
            # None = the server default (pgvector: 40), recorded as such.
            description["ef_search"] = self._ef_search
            description["candidates"] = self._candidates
        return description

    async def retrieve(self, query: str, *, k: int) -> Retrieval:
        started = time.perf_counter()
        embedding = await self._client.embed(
            EmbeddingRequest(
                model=self._spec.embedding_model,
                texts=(query,),
                data_class=self._data_class,
                dimensions=self._spec.dimensions,
                input_type="query",
            )
        )
        embedded = time.perf_counter()
        hits = await self._store.search_documents(
            self._spec,
            embedding.vectors[0],
            k=k,
            exact=self._search == "exact",
            ef_search=self._ef_search,
            candidates=self._candidates,
        )
        done = time.perf_counter()
        return Retrieval(
            documents=tuple(
                RetrievedDocument(doc_id=hit.doc_id, score=hit.score, rank=rank)
                for rank, hit in enumerate(hits, start=1)
            ),
            cost_usd=embedding.cost_usd,
            timings_ms={
                "embed": (embedded - started) * 1000.0,
                "search": (done - embedded) * 1000.0,
            },
        )
