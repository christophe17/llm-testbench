"""The regression gate (phase 2.7): refuse a push that lowers a score.

The gate runs a small suite in **sample mode** (fixtures, a simulated embedder: no network,
no key, a few seconds) and compares every metric of every arm with a versioned baseline,
``data/results/gate/baseline.json``. Everything in sample mode is deterministic, so any
drop is a change of behaviour of the code: a chunker that loses text, a join that drops
rows, a metric computed differently, a preprocessing step that moved.

What it is not: a guard on quality. Fixtures of six documents say nothing about a model or
a prompt; a regression of those shows in a full run compared with the archived one
(``make eval``), which costs money and is launched by hand. And what it cannot do: a
``pre-push`` hook is bypassed by ``--no-verify``, and the same gate in CI turns ``main``
red after the fact instead of blocking a merge (ADR 008). In a team, this check is a
required status on a protected branch.
"""

import datetime as dt
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from llm_testbench.eval.generation import GenerationRun
from llm_testbench.eval.runs import RetrievalRun, git_state

GatedRun = RetrievalRun | GenerationRun
"""Anything with an arm name and metrics that have a mean."""

GATE_SUITE = "gate"
BASELINE_PATH = Path("data") / "results" / "gate" / "baseline.json"
_EPSILON = 1e-9

Status = Literal["ok", "improved", "regression", "new", "missing", "skipped"]
FAILING: frozenset[Status] = frozenset({"regression", "new", "missing"})


class GateBaseline(BaseModel):
    model_config = ConfigDict(frozen=True)

    suite: str = GATE_SUITE
    generated_at: dt.datetime
    git_sha: str | None = None
    scores: dict[str, dict[str, float]]
    """arm -> metric -> mean, as measured in sample mode when the baseline was recorded."""

    @classmethod
    def from_runs(cls, runs: Iterable[GatedRun]) -> "GateBaseline":
        return cls(
            generated_at=dt.datetime.now(dt.UTC),
            git_sha=git_state()[0],
            scores={
                run.arm: {metric: summary.mean for metric, summary in run.metrics.items()}
                for run in runs
            },
        )

    @classmethod
    def load(cls, path: Path) -> "GateBaseline":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=1) + "\n", encoding="utf-8")


class GateFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    arm: str
    metric: str
    status: Status
    baseline: float | None = None
    current: float | None = None

    @property
    def delta(self) -> float | None:
        if self.baseline is None or self.current is None:
            return None
        return self.current - self.baseline


def check_gate(
    runs: Sequence[GatedRun],
    baseline: GateBaseline,
    *,
    max_drop: float = 0.0,
    skipped: Iterable[str] = (),
) -> list[GateFinding]:
    """One finding per (arm, metric).

    - ``regression``: the metric dropped by more than ``max_drop``;
    - ``missing``: an arm of the baseline did not run (removed, renamed: the gate would
      otherwise go quiet exactly when something disappears);
    - ``new``: an arm or a metric the baseline does not know: record it first;
    - ``skipped``: an arm that could not run here (no database) and says so;
    - ``improved`` passes, and asks for a new baseline so the gain becomes the floor.
    """
    skipped_arms = set(skipped)
    findings: list[GateFinding] = []
    ran = {run.arm for run in runs}
    for run in runs:
        expected = baseline.scores.get(run.arm, {})
        for metric, summary in run.metrics.items():
            reference = expected.get(metric)
            if reference is None:
                status: Status = "new"
            elif summary.mean < reference - max_drop - _EPSILON:
                status = "regression"
            elif summary.mean > reference + _EPSILON:
                status = "improved"
            else:
                status = "ok"
            findings.append(
                GateFinding(
                    arm=run.arm,
                    metric=metric,
                    status=status,
                    baseline=reference,
                    current=summary.mean,
                )
            )
        findings.extend(
            GateFinding(arm=run.arm, metric=metric, status="missing", baseline=value)
            for metric, value in expected.items()
            if metric not in run.metrics
        )
    for arm, expected in baseline.scores.items():
        if arm in ran:
            continue
        status = "skipped" if arm in skipped_arms else "missing"
        findings.extend(
            GateFinding(arm=arm, metric=metric, status=status, baseline=value)
            for metric, value in expected.items()
        )
    return findings


def gate_passes(findings: Iterable[GateFinding]) -> bool:
    return not any(finding.status in FAILING for finding in findings)


def format_findings(findings: Sequence[GateFinding]) -> str:
    """Only what needs a decision is listed line by line; the rest is counted."""
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.status] = counts.get(finding.status, 0) + 1
    lines = [
        f"{finding.status.upper():<10} {finding.arm:<28} {finding.metric:<16} "
        f"baseline {_show(finding.baseline)}  current {_show(finding.current)}"
        + (f"  ({finding.delta:+.4f})" if finding.delta is not None else "")
        for finding in findings
        if finding.status not in ("ok", "skipped")
    ]
    skipped_arms = sorted({f.arm for f in findings if f.status == "skipped"})
    if skipped_arms:
        lines.append(f"SKIPPED    no database reachable: {', '.join(skipped_arms)}")
    summary = ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
    verdict = "PASS" if gate_passes(findings) else "FAIL"
    lines.append(f"evaluation gate: {verdict} ({summary})")
    if any(finding.status in ("improved", "new") for finding in findings):
        lines.append("record the new scores as the baseline: make eval-gate-update")
    return "\n".join(lines)


def _show(value: float | None) -> str:
    return "     —" if value is None else f"{value:.4f}"
