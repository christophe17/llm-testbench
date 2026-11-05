"""Pipeline + DocumentSource on the real database (``db`` marker), simulated embeddings."""

import os
import uuid
from collections.abc import AsyncIterator

import pytest
from psycopg import AsyncConnection

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
    pytest.mark.skipif(DATABASE_URL is None, reason="LLM_TESTBENCH_DATABASE_URL not set"),
]


@pytest.fixture
async def store() -> AsyncIterator[PgVectorStore]:
    assert DATABASE_URL is not None
    async with PgVectorStore.from_url(DATABASE_URL, max_size=2) as store:
        await store.ensure_schema()
        yield store


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def client(embedder: FakeEmbedder) -> LLMClient:
    client = LLMClient.from_settings()
    client.register_embedder("openai", embedder)
    return client


async def test_ingest_then_search_then_cite(
    store: PgVectorStore, client: LLMClient, embedder: FakeEmbedder
) -> None:
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
    geo = "The capital of France is Paris. Paris is the capital of France. Capital: Paris."
    cook = "A recipe for pancakes. You need flour, eggs and milk. Mix, then cook."
    documents = [
        parse_text("geo", geo, title="Geo"),
        parse_text("cook", cook, title="Cooking"),
    ]
    try:
        report = await pipeline.ingest(spec, documents)
        assert report.documents_seen == 2
        assert report.documents_written == 2
        assert report.chunks_total == report.chunks_embedded
        assert report.chunks_total >= 4  # two chunks per document at chunk_size=60
        assert report.embedding_calls >= 2  # batches of 2
        assert report.cost_usd is not None
        assert report.cost_usd > 0
        assert await store.embedding_count(spec) == report.chunks_total
        # What the model saw: the document title in front of every chunk (BEIR convention).
        embedded = [text for call in embedder.calls for text in call.texts]
        assert len(embedded) == report.chunks_total
        assert all(text.startswith(("Geo ", "Cooking ")) for text in embedded)

        again = await pipeline.ingest(spec, documents)
        assert again.documents_written == 0
        assert again.chunks_embedded == 0  # nothing to pay for again
        assert again.embedding_calls == 0

        source = DocumentSource(client=client, store=store, spec=spec)
        assert Capability.SEARCH in source.capabilities
        evidence = await source.search(
            SearchQuery(text="What is the capital?", k=2, data_class=DataClass.PUBLIC)
        )
        assert [e.rank for e in evidence] == [1, 2]
        assert evidence[0].provenance.document_id == "geo"
        assert evidence[0].provenance.title == "Geo"
        assert evidence[0].provenance.extra == {"index_key": spec.index_key}
        assert evidence[0].score == pytest.approx(1.0, abs=1e-6)
        assert (
            Citation.from_evidence(1, evidence[0]).render().startswith(f"[1] {source_key} › Geo › ")
        )

        whole = await source.fetch("geo")
        assert whole is not None
        assert "Paris" in whole.text
        assert whole.provenance.locator == "whole document"
        assert await source.fetch("nope") is None

        info = await source.describe()
        assert info.document_count == 2
        assert info.key == source_key

        # A new title changes what the model sees: that document, and only it, is embedded again.
        retitled = [documents[0].model_copy(update={"title": "Geography"}), documents[1]]
        third = await pipeline.ingest(spec, retitled)
        assert third.documents_written == 1
        assert 0 < third.chunks_embedded < report.chunks_total
        assert all(text.startswith("Geography ") for text in embedder.calls[-1].texts)
    finally:
        await store.drop_index(spec.index_key)
        await store.delete_source(source_key)


async def _analyzed_at(table: str) -> object:
    assert DATABASE_URL is not None
    async with await AsyncConnection.connect(DATABASE_URL) as conn:
        cursor = await conn.execute(
            "SELECT last_analyze FROM pg_stat_user_tables WHERE relname = %s", (table,)
        )
        row = await cursor.fetchone()
    return row[0] if row else None


async def test_a_load_refreshes_the_planner_statistics_and_a_no_op_does_not(
    store: PgVectorStore, client: LLMClient
) -> None:
    """A bulk load the planner has no statistics for is run with a plan made for one row
    (22 seconds for one search, measured on 2026-11-05): the pipeline analyzes what it
    filled. An ingestion that writes nothing leaves the statistics alone."""
    suffix = uuid.uuid4().hex[:8]
    pipeline = IngestionPipeline(
        client=client, store=store, chunker=RecursiveChunker(), data_class=DataClass.PUBLIC
    )
    spec = pipeline.index_spec(
        index_key=f"t-{suffix}",
        source_key=f"docs:test-{suffix}",
        embedding_model="openai/text-embedding-3-small",
        dimensions=2,
    )
    documents = [parse_text(f"doc-{number}", f"Text number {number}.") for number in range(5)]
    try:
        await store.register_index(spec)
        assert await _analyzed_at(spec.table) is None
        await pipeline.ingest(spec, documents)
        first = await _analyzed_at(spec.table)
        assert first is not None
        again = await pipeline.ingest(spec, documents)
        assert again.documents_written == again.chunks_embedded == 0
        assert await _analyzed_at(spec.table) == first
    finally:
        await store.drop_index(spec.index_key)
        await store.delete_source(spec.source_key)


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
