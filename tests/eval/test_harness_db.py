"""The harness on a real database (``db`` marker): a dense arm end to end, the history."""

import os
import uuid
from pathlib import Path

import pytest

from llm_testbench.config import Settings
from llm_testbench.eval.cli import run_suite
from llm_testbench.eval.run_store import RunStore
from llm_testbench.eval.suite import ArmConfig, SuiteConfig, run_arm
from llm_testbench.ingest.chunking import RecursiveChunker
from llm_testbench.ingest.parsing import parse_sections
from llm_testbench.ingest.pipeline import IngestionPipeline
from llm_testbench.ingest.store import PgVectorStore
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.testing import HashingEmbedder
from llm_testbench.sources.documents import DocumentSource
from llm_testbench.sources.types import SearchQuery
from tests.conftest import FIXTURES_DIR

DATABASE_URL = os.environ.get("LLM_TESTBENCH_DATABASE_URL")

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(DATABASE_URL is None, reason="LLM_TESTBENCH_DATABASE_URL not set"),
]


@pytest.fixture
def sample_settings(tmp_path: Path) -> Settings:
    return Settings(
        fixtures_dir=FIXTURES_DIR,
        data_dir=tmp_path / "cache",
        sample=True,
        database_url=DATABASE_URL,
    )


async def test_dense_arm_in_sample_mode_builds_measures_and_cleans_up(
    sample_settings: Settings,
) -> None:
    # A dataset name of its own: the sample index must not collide with a parallel run.
    arm = ArmConfig(
        name="dense",
        dataset="beir/scifact",
        retriever="dense",
        embedding_model="openai/text-embedding-3-small",
        chunk_size=0,
        search="exact",
    )
    index_key, source_key = arm.keys(sample=True)
    assert DATABASE_URL is not None
    async with PgVectorStore.from_url(DATABASE_URL, max_size=2) as store:
        run = await run_arm(
            "unit",
            SuiteConfig(arms=(arm,)),
            arm,
            settings=sample_settings,
            client=LLMClient.from_settings(sample_settings),
            store=store,
        )
        # The bag of hashed words is lexical: fixture queries share words with their
        # relevant document, so it is found, with no model and no network.
        assert run.metrics["recall_at_10"].mean == pytest.approx(1.0)
        assert run.sample_mode
        assert not run.publishable
        assert run.retriever["search"] == "exact"
        assert run.retriever["embedding_model"] == "openai/text-embedding-3-small"
        assert run.index is not None
        assert run.index.chunks_embedded == run.index.chunks > 0
        assert run.timings_ms.keys() == {"embed", "search"}
        # Sample indexes are dropped after the run.
        assert await store.get_index(index_key) is None
        assert await store.counts(source_key) == (0, 0)


async def test_run_history_round_trip(sample_settings: Settings) -> None:
    assert DATABASE_URL is not None
    history = RunStore(DATABASE_URL)
    await history.ensure_schema()
    await history.ensure_schema()  # idempotent
    arm = ArmConfig(name="bm25", dataset="beir/scifact", retriever="bm25")
    suite_name = f"unit-{uuid.uuid4().hex[:8]}"
    run = await run_arm(
        suite_name,
        SuiteConfig(arms=(arm,)),
        arm,
        settings=sample_settings,
        client=LLMClient.from_settings(sample_settings),
        store=None,
    )
    await history.save(run)
    try:
        assert await history.get(run.run_id) == run
        rows = await history.history(suite_name)
        assert [row["run_id"] for row in rows] == [run.run_id]
        assert rows[0]["publishable"] is False
        assert rows[0]["metrics"]["ndcg_at_10"]["mean"] == pytest.approx(
            run.metrics["ndcg_at_10"].mean
        )
        assert await history.history(suite_name, arm="other") == []
    finally:
        await history.delete(run.run_id)
    assert await history.get(run.run_id) is None


async def test_cli_runs_the_versioned_suite_in_sample_mode(
    sample_settings: Settings, tmp_path: Path
) -> None:
    """Every arm of ``config/eval_suites.toml`` runs end to end on fixtures: the suite file
    cannot rot. Nothing is archived, since nothing here is a number."""
    runs = await run_suite(
        "retrieval-baseline",
        ["scifact-bm25", "scifact-bge-whole-exact", "nfcorpus-oai-chunks-hnsw"],
        settings=sample_settings,
        results_dir=tmp_path,
        echo=False,
    )
    assert [run.arm for run in runs] == [
        "scifact-bm25",
        "scifact-bge-whole-exact",
        "nfcorpus-oai-chunks-hnsw",
    ]
    assert not any(run.publishable for run in runs)
    assert not (tmp_path / "runs").exists()
    assert DATABASE_URL is not None
    history = RunStore(DATABASE_URL)
    for run in runs:
        assert await history.get(run.run_id) is not None
        await history.delete(run.run_id)


async def test_a_scoped_search_only_returns_chunks_of_the_scoped_document(
    tmp_path: Path,
) -> None:
    """QASPER asks a question about one paper: the search carries the paper as a filter.
    Sixty documents sit nearer to the question than the one the filter wants; the wanted
    one still comes back, alone."""
    assert DATABASE_URL is not None
    settings = Settings(
        fixtures_dir=FIXTURES_DIR, data_dir=tmp_path / "cache", database_url=DATABASE_URL
    )
    client = LLMClient.from_settings(settings)
    client.register_embedder("openai", HashingEmbedder(dimensions=64))
    suffix = uuid.uuid4().hex[:8]
    crowd = [
        parse_sections(
            f"crowd-{number}",
            [("", f"baseline accuracy results table {number}")],
            metadata={"paper_id": "crowd"},
        )
        for number in range(60)
    ]
    wanted = parse_sections(
        "wanted",
        [("", "baseline accuracy mentioned once among unrelated words about tokenizers")],
        metadata={"paper_id": "wanted"},
    )
    async with PgVectorStore.from_url(DATABASE_URL, max_size=2) as store:
        pipeline = IngestionPipeline(
            client=client, store=store, chunker=RecursiveChunker(), data_class=DataClass.PUBLIC
        )
        spec = pipeline.index_spec(
            index_key=f"sample-filter-{suffix}",
            source_key=f"sample:filter-{suffix}",
            embedding_model="openai/text-embedding-3-small",
            dimensions=64,
        )
        try:
            await pipeline.ingest(spec, [*crowd, wanted])
            source = DocumentSource(client=client, store=store, spec=spec)

            async def search(filters: dict[str, str]) -> list[str]:
                query = SearchQuery(
                    text="baseline accuracy results table",
                    k=5,
                    filters=filters,
                    data_class=DataClass.PUBLIC,
                )
                return [item.provenance.document_id for item in await source.search(query)]

            assert await search({"paper_id": "wanted"}) == ["wanted"]
            unscoped = await search({})
            assert len(unscoped) == 5
            assert "wanted" not in unscoped
        finally:
            await store.drop_index(spec.index_key)
            await store.delete_source(spec.source_key)
