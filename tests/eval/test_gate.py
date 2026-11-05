from pathlib import Path

import pytest

from llm_testbench.config import Settings
from llm_testbench.eval.gate import (
    GateBaseline,
    check_gate,
    format_findings,
    gate_passes,
)
from llm_testbench.eval.runs import MetricSummary, RetrievalRun
from llm_testbench.eval.suite import ArmConfig, SuiteConfig, run_arm
from llm_testbench.llm.client import LLMClient


@pytest.fixture
async def run(offline_settings: Settings) -> RetrievalRun:
    arm = ArmConfig(name="scifact-bm25", dataset="beir/scifact", retriever="bm25")
    return await run_arm(
        "gate",
        SuiteConfig(arms=(arm,), metrics=("ndcg_at_10", "recall_at_10")),
        arm,
        settings=offline_settings,
        client=LLMClient.from_settings(offline_settings),
        store=None,
    )


def with_score(run: RetrievalRun, metric: str, value: float) -> RetrievalRun:
    metrics = {**run.metrics, metric: MetricSummary(mean=value, low=value, high=value)}
    return run.model_copy(update={"metrics": metrics})


def statuses(findings: list) -> dict[tuple[str, str], str]:  # type: ignore[type-arg]
    return {(finding.arm, finding.metric): finding.status for finding in findings}


def test_identical_scores_pass(run: RetrievalRun, tmp_path: Path) -> None:
    baseline = GateBaseline.from_runs([run])
    baseline.save(tmp_path / "gate" / "baseline.json")
    assert GateBaseline.load(tmp_path / "gate" / "baseline.json") == baseline
    findings = check_gate([run], baseline)
    assert set(statuses(findings).values()) == {"ok"}
    assert gate_passes(findings)
    assert "PASS" in format_findings(findings)


def test_a_drop_fails_and_names_the_metric(run: RetrievalRun) -> None:
    baseline = GateBaseline.from_runs([run])
    worse = with_score(run, "ndcg_at_10", run.metrics["ndcg_at_10"].mean - 0.05)
    findings = check_gate([worse], baseline)
    assert statuses(findings) == {
        ("scifact-bm25", "ndcg_at_10"): "regression",
        ("scifact-bm25", "recall_at_10"): "ok",
    }
    assert not gate_passes(findings)
    report = format_findings(findings)
    assert "REGRESSION" in report
    assert "(-0.0500)" in report
    assert "FAIL" in report


def test_a_drop_within_the_tolerance_passes(run: RetrievalRun) -> None:
    baseline = GateBaseline.from_runs([run])
    worse = with_score(run, "ndcg_at_10", run.metrics["ndcg_at_10"].mean - 0.01)
    assert gate_passes(check_gate([worse], baseline, max_drop=0.02))
    assert not gate_passes(check_gate([worse], baseline, max_drop=0.005))


def test_an_improvement_passes_and_asks_for_a_new_baseline(run: RetrievalRun) -> None:
    lower = with_score(run, "ndcg_at_10", run.metrics["ndcg_at_10"].mean - 0.1)
    findings = check_gate([run], GateBaseline.from_runs([lower]))
    assert statuses(findings)[("scifact-bm25", "ndcg_at_10")] == "improved"
    assert gate_passes(findings)
    assert "make eval-gate-update" in format_findings(findings)


def test_an_arm_that_disappears_fails_unless_it_was_skipped(run: RetrievalRun) -> None:
    other = run.model_copy(update={"arm": "scifact-dense"})
    baseline = GateBaseline.from_runs([run, other])
    assert not gate_passes(check_gate([run], baseline))
    skipped = check_gate([run], baseline, skipped=["scifact-dense"])
    assert gate_passes(skipped)
    assert "SKIPPED    no database reachable: scifact-dense" in format_findings(skipped)


def test_an_unknown_arm_or_metric_fails_until_recorded(run: RetrievalRun) -> None:
    baseline = GateBaseline.from_runs([run])
    renamed = run.model_copy(update={"arm": "renamed"})
    findings = check_gate([renamed], baseline)
    assert set(statuses(findings).values()) == {"new", "missing"}
    assert not gate_passes(findings)
    dropped = run.model_copy(
        update={"metrics": {"ndcg_at_10": run.metrics["ndcg_at_10"]}},
    )
    assert statuses(check_gate([dropped], baseline))[("scifact-bm25", "recall_at_10")] == "missing"


async def test_the_gate_runs_without_a_database_and_says_what_it_skipped(
    offline_settings: Settings,
) -> None:
    """The laptop case: cluster down. The arms that need no database still run."""
    from llm_testbench.eval.cli import run_gate

    unreachable = offline_settings.model_copy(
        update={"database_url": "postgresql://nobody:x@127.0.0.1:1/none"}
    )
    runs, skipped = await run_gate(unreachable, require_db=False)
    assert [run.arm for run in runs] == [
        "scifact-bm25",
        "nfcorpus-bm25",
        "hotpotqa-bm25",
        "squad-gold",
        "hotpotqa-gold",
        "squad-closed-book",
        "qasper-gold",
    ]
    # Everything that reads a pgvector index: dense retrieval and searched contexts.
    assert skipped == [
        "scifact-dense-whole-exact",
        "scifact-dense-chunks-hnsw",
        "nfcorpus-dense-chunks-exact",
        "hotpotqa-retrieved",
        "qasper-retrieved",
    ]
    assert not any(run.publishable for run in runs)
    with pytest.raises(SystemExit, match="database is required"):
        await run_gate(unreachable, require_db=True)
