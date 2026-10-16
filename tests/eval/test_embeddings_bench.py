import datetime as dt
from pathlib import Path

import numpy as np
import pytest

from llm_testbench.eval.embeddings_bench import (
    PUBLISHED_SCIFACT,
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
                published_source="carte HF",
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
    assert "0.0300 $" in table
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
    batches = [{"text": ["capitale a", "capitale b"]}, {"text": ["recette"]}]
    vectors = encoder.encode(iter(batches))
    assert isinstance(vectors, np.ndarray)
    assert vectors.shape == (3, 2)
    assert encoder.calls == 2
    assert encoder.cost_usd is not None
    assert encoder.cost_usd > 0
    assert encoder.mteb_model_meta.name == "openai/text-embedding-3-small"
    assert all(r.data_class.value == "public" for r in embedder.calls)
