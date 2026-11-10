import datetime as dt
from pathlib import Path

import pytest

from llm_testbench.config import Settings
from llm_testbench.eval.loaders import BeirLoader
from llm_testbench.eval.report import render_report, write_report
from llm_testbench.eval.runner import run_retrieval
from llm_testbench.eval.runs import Reference, RetrievalRun, save_retrieval_run
from llm_testbench.eval.suite import RetrievalArmConfig, SuiteConfig
from tests.eval.test_runner import ScriptedRetriever, rankings


@pytest.fixture
async def runs(offline_settings: Settings) -> list[RetrievalRun]:
    dataset = BeirLoader("scifact", settings=offline_settings).load("test")
    good = rankings(dataset)
    bad = {query: ["21389"] for query in good}
    reference = Reference(label="paper <b>", value=0.9, source="a table")
    return [
        await run_retrieval(
            dataset, ScriptedRetriever(bad), suite="unit", arm="bad", resamples=100
        ),
        await run_retrieval(
            dataset,
            ScriptedRetriever(good),
            suite="unit",
            arm="good",
            references=[reference],
            resamples=100,
        ),
    ]


def suite() -> SuiteConfig:
    arms = tuple(
        RetrievalArmConfig(name=name, dataset="beir/scifact", retriever="bm25")
        for name in ("bad", "good", "never-run")
    )
    return SuiteConfig(description="A suite for the tests.", retrieval=arms)


def test_report_shows_scores_intervals_references_and_comparisons(
    runs: list[RetrievalRun],
) -> None:
    html = render_report(
        "unit", suite(), list(reversed(runs)), generated_at=dt.datetime(2026, 11, 5, tzinfo=dt.UTC)
    )
    good = runs[1]
    assert f"<strong>{good.metrics['ndcg_at_10'].mean:.3f}</strong>" in html
    assert f"({good.gap(good.references[0]):+.3f})" in html
    # Suite order, not file order: the comparison baseline is the first arm of the suite.
    assert html.index('data-arm="bad"') < html.index('data-arm="good"')
    assert "Paired comparison with bad, same queries" in html
    assert "never-run" in html  # an arm without an archived run is named
    assert "beir/scifact" in html
    assert "Generated 2026-11-05" in html
    # Labels come from configuration files: escaped, never markup.
    assert "paper &lt;b&gt;" in html
    assert "paper <b>" not in html


def test_report_is_written_from_the_archive(runs: list[RetrievalRun], tmp_path: Path) -> None:
    for run in runs:
        save_retrieval_run(run, tmp_path)
    path, count = write_report("unit", suite(), tmp_path, tmp_path / "out" / "unit.html")
    assert count == 2
    assert path.read_text(encoding="utf-8").startswith("<!doctype html>")
    with pytest.raises(FileNotFoundError, match="make eval"):
        write_report("empty", suite(), tmp_path, tmp_path / "out" / "empty.html")
