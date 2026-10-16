"""Pipeline + DocumentSource sur la vraie base (marqueur ``db``), embeddings simulés."""

import os
import uuid
from collections.abc import AsyncIterator

import pytest

from llm_testbench.ingest.chunking import RecursiveChunker
from llm_testbench.ingest.parsing import parse_text
from llm_testbench.ingest.pipeline import IngestionPipeline
from llm_testbench.ingest.store import PgVectorStore
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.governance import DataClass
from llm_testbench.sources import Capability, Citation, SearchQuery
from llm_testbench.sources.documents import DocumentSource
from tests.llm.fakes import FakeEmbedder

DATABASE_URL = os.environ.get("LLM_TESTBENCH_DATABASE_URL")

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(DATABASE_URL is None, reason="LLM_TESTBENCH_DATABASE_URL non défini"),
]


@pytest.fixture
async def store() -> AsyncIterator[PgVectorStore]:
    assert DATABASE_URL is not None
    async with PgVectorStore.from_url(DATABASE_URL, max_size=2) as store:
        await store.ensure_schema()
        yield store


@pytest.fixture
def client() -> LLMClient:
    client = LLMClient.from_settings()
    client.register_embedder("openai", FakeEmbedder())
    return client


async def test_ingest_then_search_then_cite(store: PgVectorStore, client: LLMClient) -> None:
    source_key = f"docs:test-{uuid.uuid4().hex[:8]}"
    pipeline = IngestionPipeline(
        client=client,
        store=store,
        chunker=RecursiveChunker(chunk_size=60, chunk_overlap=0),
        data_class=DataClass.PUBLIC,
        batch_size=2,
    )
    spec = pipeline.index_spec(
        index_key=f"t-{uuid.uuid4().hex[:8]}",
        source_key=source_key,
        embedding_model="openai/text-embedding-3-small",
        dimensions=2,
        description="test",
    )
    geo = (
        "La capitale de la France est Paris. Paris est la capitale de la France. Capitale : Paris."
    )
    cook = "Une recette de crêpes. Il faut de la farine, des œufs et du lait. Mélanger, puis cuire."
    documents = [
        parse_text("geo", geo, title="Géo"),
        parse_text("cook", cook, title="Cuisine"),
    ]
    try:
        report = await pipeline.ingest(spec, documents)
        assert report.documents_seen == 2
        assert report.documents_written == 2
        assert report.chunks_total == report.chunks_embedded
        assert report.chunks_total >= 4  # deux chunks par document à chunk_size=60
        assert report.embedding_calls >= 2  # lots de 2
        assert report.cost_usd is not None
        assert report.cost_usd > 0
        assert await store.embedding_count(spec) == report.chunks_total

        again = await pipeline.ingest(spec, documents)
        assert again.documents_written == 0
        assert again.chunks_embedded == 0  # rien à repayer
        assert again.embedding_calls == 0

        source = DocumentSource(client=client, store=store, spec=spec)
        assert Capability.SEARCH in source.capabilities
        evidence = await source.search(
            SearchQuery(text="Quelle est la capitale ?", k=2, data_class=DataClass.PUBLIC)
        )
        assert [e.rank for e in evidence] == [1, 2]
        assert evidence[0].provenance.document_id == "geo"
        assert evidence[0].provenance.title == "Géo"
        assert evidence[0].provenance.extra == {"index_key": spec.index_key}
        assert evidence[0].score == pytest.approx(1.0, abs=1e-6)
        assert (
            Citation.from_evidence(1, evidence[0]).render().startswith(f"[1] {source_key} › Géo › ")
        )

        whole = await source.fetch("geo")
        assert whole is not None
        assert "Paris" in whole.text
        assert whole.provenance.locator == "document entier"
        assert await source.fetch("nope") is None

        info = await source.describe()
        assert info.document_count == 2
        assert info.key == source_key
    finally:
        await store.drop_index(spec.index_key)
        await store.delete_source(source_key)


async def test_pipeline_refuses_an_index_built_with_another_chunker(
    store: PgVectorStore, client: LLMClient
) -> None:
    pipeline = IngestionPipeline(
        client=client,
        store=store,
        chunker=RecursiveChunker(chunk_size=60, chunk_overlap=0),
        data_class=DataClass.PUBLIC,
    )
    spec = pipeline.index_spec(
        index_key="never-created",
        source_key="docs:never",
        embedding_model="openai/text-embedding-3-small",
        dimensions=2,
    )
    other = IngestionPipeline(
        client=client,
        store=store,
        chunker=RecursiveChunker(chunk_size=61, chunk_overlap=0),
        data_class=DataClass.PUBLIC,
    )
    with pytest.raises(ValueError, match="chunker"):
        await other.ingest(spec, [])
