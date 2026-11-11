"""The runner on a scripted retriever: every number of the record is checked by hand."""

from pathlib import Path

import pytest

from llm_testbench.config import Settings
from llm_testbench.eval.loaders import BeirLoader
from llm_testbench.eval.retrieval import (
    Reference,
    format_retrieval_runs,
    load_retrieval_run,
    run_retrieval,
    save_retrieval_run,
)
from llm_testbench.eval.types import RetrievalDataset
from llm_testbench.retrieval import Description, Retrieval, RetrievedDocument


class ScriptedRetriever:
    """Returns a fixed ranking per query text and counts its calls."""

    def __init__(self, rankings: dict[str, list[str]], cost_usd: float | None = 0.001) -> None:
        self._rankings = rankings
        self._cost_usd = cost_usd
        self.calls: list[tuple[str, int]] = []

    def describe(self) -> Description:
        return {"retriever": "scripted"}

    async def retrieve(self, query: str, *, k: int) -> Retrieval:
        self.calls.append((query, k))
        return Retrieval(
            documents=tuple(
                RetrievedDocument(doc_id=doc_id, score=1.0 / rank, rank=rank)
                for rank, doc_id in enumerate(self._rankings[query][:k], start=1)
            ),
            cost_usd=self._cost_usd,
            timings_ms={"embed": 2.0, "search": 1.0},
        )


@pytest.fixture
def dataset(offline_settings: Settings) -> RetrievalDataset:
    return BeirLoader("scifact", settings=offline_settings).load("test")


def rankings(dataset: RetrievalDataset) -> dict[str, list[str]]:
    by_id = {query.query_id: query.text for query in dataset.queries}
    return {
        by_id["1"]: ["4983", "21389", "5836"],  # both relevant, at ranks 1 and 3
        by_id["3"]: ["21389", "19238"],  # the relevant one at rank 2
        by_id["5"]: ["21389"],  # missed
    }


async def test_run_summarizes_metrics_latency_and_cost(dataset: RetrievalDataset) -> None:
    retriever = ScriptedRetriever(rankings(dataset))
    run = await run_retrieval(
        dataset,
        retriever,
        suite="unit",
        arm="scripted",
        metrics=["recall_at_10", "mrr_at_10", "precision_at_10"],
        resamples=200,
    )
    assert run.metrics["recall_at_10"].mean == pytest.approx((1.0 + 1.0 + 0.0) / 3)
    assert run.metrics["mrr_at_10"].mean == pytest.approx((1.0 + 0.5 + 0.0) / 3)
    assert run.metrics["precision_at_10"].mean == pytest.approx((0.2 + 0.1 + 0.0) / 3)
    interval = run.metrics["recall_at_10"]
    assert interval.low <= interval.mean <= interval.high
    assert run.per_query("mrr_at_10") == {"1": 1.0, "3": 0.5, "5": 0.0}
    assert run.queries[0].ranking == ("4983", "21389", "5836")
    assert run.depth == 10
    assert run.cost_usd == pytest.approx(0.003)
    assert run.timings_ms == {"embed": pytest.approx(2.0), "search": pytest.approx(1.0)}
    assert set(run.latency_ms) == {"mean", "p50", "p95"}
    assert run.dataset["dataset"] == "beir/scifact"
    assert run.retriever == {"retriever": "scripted"}
    # One unmeasured warm-up call, then one call per query, at the depth of the metrics.
    assert len(retriever.calls) == 4
    assert {k for _, k in retriever.calls} == {10}


async def test_an_unknown_cost_makes_the_run_cost_unknown(dataset: RetrievalDataset) -> None:
    run = await run_retrieval(
        dataset,
        ScriptedRetriever(rankings(dataset), cost_usd=None),
        suite="unit",
        arm="scripted",
        resamples=50,
    )
    assert run.cost_usd is None
    assert "unknown" in format_retrieval_runs([run])


async def test_reference_gap_and_table(dataset: RetrievalDataset) -> None:
    reference = Reference(label="paper", value=0.5, source="a table", metric="mrr_at_10")
    run = await run_retrieval(
        dataset,
        ScriptedRetriever(rankings(dataset)),
        suite="unit",
        arm="scripted",
        references=[reference],
        resamples=50,
    )
    assert run.gap(reference) == pytest.approx(0.0)
    table = format_retrieval_runs([run])
    assert "scripted" in table
    assert "0.500 paper (+0.000)" in table


async def test_a_full_run_is_archived_and_a_sample_run_is_not(
    dataset: RetrievalDataset, offline_settings: Settings, tmp_path: Path
) -> None:
    retriever = ScriptedRetriever(rankings(dataset))
    run = await run_retrieval(dataset, retriever, suite="unit", arm="scripted", resamples=50)
    assert run.publishable
    path = save_retrieval_run(run, tmp_path)
    assert path == tmp_path / "runs" / "unit" / "scripted.json"
    assert load_retrieval_run(path) == run
    # One line per query, after the indented summary.
    text = path.read_text(encoding="utf-8")
    assert text.count('\n  {"query_id"') == len(run.queries)

    sampled = BeirLoader("scifact", settings=offline_settings).load("test", max_queries=2)
    sample_run = await run_retrieval(sampled, retriever, suite="unit", arm="s", resamples=50)
    assert not sample_run.publishable
    assert "NOT PUBLISHABLE" in format_retrieval_runs([sample_run])
    with pytest.raises(ValueError, match="not publishable"):
        save_retrieval_run(sample_run, tmp_path)

    on_fixtures = await run_retrieval(
        dataset, retriever, suite="unit", arm="s", sample_mode=True, resamples=50
    )
    assert not on_fixtures.publishable


async def test_a_retriever_returning_a_document_twice_fails_the_run(
    dataset: RetrievalDataset,
) -> None:
    broken = {query.text: ["4983", "4983"] for query in dataset.queries}
    with pytest.raises(ValueError, match="more than once"):
        await run_retrieval(dataset, ScriptedRetriever(broken), suite="unit", arm="broken")
