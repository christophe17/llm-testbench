import pytest

from llm_testbench.config import Settings
from llm_testbench.eval.compare import compare_runs, describe_difference
from llm_testbench.eval.loaders import BeirLoader
from llm_testbench.eval.retrieval import run_retrieval
from tests.eval.test_retrieval import ScriptedRetriever, rankings


async def test_two_runs_are_compared_query_by_query(offline_settings: Settings) -> None:
    dataset = BeirLoader("scifact", settings=offline_settings).load("test")
    good = rankings(dataset)
    bad = {query: ["21389"] for query in good}  # the distractor only: every query missed
    kwargs = {"suite": "unit", "metrics": ["mrr_at_10"], "resamples": 200}
    candidate = await run_retrieval(dataset, ScriptedRetriever(good), arm="good", **kwargs)  # type: ignore[arg-type]
    baseline = await run_retrieval(dataset, ScriptedRetriever(bad), arm="bad", **kwargs)  # type: ignore[arg-type]

    difference = compare_runs(candidate, baseline, "mrr_at_10", resamples=200)
    assert difference.mean == pytest.approx(0.5)
    assert "Δ mrr_at_10 = +0.5000" in describe_difference(difference, "mrr_at_10")
    same = compare_runs(candidate, candidate, "mrr_at_10", resamples=200)
    assert same.mean == 0.0
    assert "no significant difference" in describe_difference(same, "mrr_at_10")

    fewer = BeirLoader("scifact", settings=offline_settings).load("test", max_queries=2)
    partial = await run_retrieval(fewer, ScriptedRetriever(good), arm="partial", **kwargs)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="same queries"):
        compare_runs(partial, baseline, "mrr_at_10")
