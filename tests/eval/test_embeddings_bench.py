import asyncio
import datetime as dt
from pathlib import Path

import numpy as np
import pytest

from llm_testbench.eval.embeddings_bench import (
    PUBLISHED_SCIFACT,
    BackgroundLoop,
    BenchmarkReport,
    ModelScore,
    load_report,
    save_report,
)
from llm_testbench.llm.client import LLMClient
from tests.llm.fakes import FakeEmbedder


def test_report_round_trip_and_table(tmp_path: Path) -> None:
    report = BenchmarkReport(
        generated_at=dt.datetime(2026, 9, 3, tzinfo=dt.UTC),
        scores=(
            ModelScore(
                model="BAAI/bge-base-en-v1.5",
                ndcg_at_10=0.741,
                dimensions=768,
                elapsed_s=120.0,
                published_ndcg_at_10=0.7404,
                published_source="HF card",
            ),
            ModelScore(
                model="openai/x", ndcg_at_10=0.7, elapsed_s=3.0, cost_usd=0.03, backend="openai"
            ),
        ),
    )
    path = tmp_path / "r.json"
    save_report(report, path)
    assert load_report(path) == report
    table = report.table()
    assert "+0.001" in table
    assert "$0.0300" in table
    assert report.scores[1].gap_to_published is None


def test_published_scores_carry_a_source() -> None:
    for value, source in PUBLISHED_SCIFACT.values():
        assert source
        assert value is None or 0 < value < 1


def test_client_encoder_routes_batches_through_the_facade() -> None:
    pytest.importorskip("mteb")
    from llm_testbench.eval.embeddings_bench import ClientEncoder

    client = LLMClient.from_settings()
    embedder = FakeEmbedder()
    client.register_embedder("openai", embedder)
    encoder = ClientEncoder(client, "openai/text-embedding-3-small")
    batches = [{"text": ["capital a", "capital b"]}, {"text": ["recipe"]}]
    vectors = encoder.encode(iter(batches))
    assert isinstance(vectors, np.ndarray)
    assert vectors.shape == (3, 2)
    assert encoder.calls == 2
    assert encoder.cost_usd is not None
    assert encoder.cost_usd > 0
    assert encoder.mteb_model_meta.name == "openai/text-embedding-3-small"
    assert all(r.data_class.value == "public" for r in embedder.calls)
    encoder.close()


def test_client_encoder_follows_the_mteb_encoder_protocol() -> None:
    pytest.importorskip("mteb")
    from mteb.models.models_protocols import EncoderProtocol

    from llm_testbench.eval.embeddings_bench import ClientEncoder

    encoder = ClientEncoder(LLMClient.from_settings(), "openai/text-embedding-3-small")
    # mteb checks the protocol with isinstance before the first batch: a missing method is a
    # TypeError at evaluation time, not a typing detail.
    assert isinstance(encoder, EncoderProtocol)
    queries = np.asarray([[1.0, 0.0], [0.0, 2.0]], dtype=np.float32)
    documents = np.asarray([[3.0, 0.0], [0.0, 1.0], [1.0, 1.0]], dtype=np.float32)
    scores = np.asarray(encoder.similarity(queries, documents))
    assert scores.shape == (2, 3)
    assert scores[0, 0] == pytest.approx(1.0)  # cosine: the norm does not count
    assert scores[0, 1] == pytest.approx(0.0)
    pairwise = np.asarray(encoder.similarity_pairwise(queries, documents[:2]))
    assert pairwise == pytest.approx([1.0, 1.0])
    encoder.close()


async def test_client_encoder_encodes_from_inside_a_running_loop() -> None:
    # A notebook cell: a synchronous call made while the kernel's event loop is running.
    pytest.importorskip("mteb")
    from llm_testbench.eval.embeddings_bench import ClientEncoder

    client = LLMClient.from_settings()
    client.register_embedder("openai", FakeEmbedder())
    encoder = ClientEncoder(client, "openai/text-embedding-3-small")
    vectors = encoder.encode(iter([{"text": ["capital a"]}, {"text": ["recipe"]}]))
    assert vectors.shape == (2, 2)
    assert encoder.calls == 2
    encoder.close()


async def test_background_loop_serves_a_caller_whose_own_loop_is_running() -> None:
    async def running_loop() -> asyncio.AbstractEventLoop:
        return asyncio.get_running_loop()

    async def fail() -> None:
        raise ValueError("from the coroutine")

    loop = BackgroundLoop()
    try:
        first, second = loop.run(running_loop()), loop.run(running_loop())
        # asyncio.run would refuse to start here, and would open a new loop per call.
        assert first is second
        assert first is not asyncio.get_running_loop()
        with pytest.raises(ValueError, match="from the coroutine"):
            loop.run(fail())
    finally:
        loop.close()
    assert first.is_closed()
