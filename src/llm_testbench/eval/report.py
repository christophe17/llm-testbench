"""The comparative HTML report of a suite (phase 2.7), built from the archived runs.

One section per dataset: a plot of each arm's nDCG@10 with its bootstrap interval and the
reference score it is compared to, the table of every metric with latency and cost, and
the paired comparison of each arm with the first arm of the dataset (the lexical baseline).
The plot is there for one reading the table makes hard: whether two intervals overlap, and
how far a score sits from its reference.

The report is derived data: it is rebuilt from ``data/results/runs/`` at any time, without
running anything, and written under ``build/`` (not versioned). One self-contained file, no
network: it opens from the disk.
"""

import datetime as dt
import math
from collections.abc import Sequence
from importlib import resources
from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined

from llm_testbench.eval.compare import compare_runs
from llm_testbench.eval.runs import HEADLINE_METRIC, RetrievalRun, load_run
from llm_testbench.eval.suite import SuiteConfig

TEMPLATE = "report.html.j2"

# Geometry of a plot, in SVG user units (the SVG scales with the page width).
WIDTH = 760
GUTTER = 250  # arm names
RIGHT = 24
ROW = 30
TOP = 8
AXIS = 26


def _domain(values: Sequence[float]) -> tuple[float, float, float]:
    """(low, high, tick step): bounds rounded outward to a clean tick."""
    low, high = min(values), max(values)
    step = 0.05 if high - low <= 0.3 else 0.1
    low = math.floor(low / step) * step
    high = math.ceil(high / step) * step
    if high - low < step:
        high = low + step
    return low, high, step


def _panel(runs: Sequence[RetrievalRun]) -> dict[str, Any]:
    """Positions of every mark of one dataset's plot."""
    values: list[float] = []
    for run in runs:
        headline = run.metrics[HEADLINE_METRIC]
        values += [headline.low, headline.high]
        values += [ref.value for ref in run.references if ref.metric == HEADLINE_METRIC]
    low, high, step = _domain(values)
    span = WIDTH - GUTTER - RIGHT

    def x(value: float) -> float:
        return round(GUTTER + (value - low) / (high - low) * span, 1)

    rows = []
    for position, run in enumerate(runs):
        headline = run.metrics[HEADLINE_METRIC]
        references = [ref for ref in run.references if ref.metric == HEADLINE_METRIC]
        rows.append(
            {
                "arm": run.arm,
                "y": TOP + position * ROW + ROW / 2,
                "top": TOP + position * ROW,
                "mean": headline.mean,
                "low": headline.low,
                "high": headline.high,
                "x_mean": x(headline.mean),
                "x_low": x(headline.low),
                "x_high": x(headline.high),
                "reference": (
                    {
                        "x": x(references[0].value),
                        "value": references[0].value,
                        "label": references[0].label,
                        "gap": run.gap(references[0]),
                    }
                    if references
                    else None
                ),
            }
        )
    ticks = []
    count = round((high - low) / step)
    for index in range(count + 1):
        value = low + index * step
        ticks.append({"x": x(value), "label": f"{value:.2f}"})
    plot_bottom = TOP + len(runs) * ROW
    return {
        "rows": rows,
        "ticks": ticks,
        "width": WIDTH,
        "height": plot_bottom + AXIS,
        "plot_bottom": plot_bottom,
        "gutter": GUTTER,
        "row": ROW,
    }


def _comparisons(runs: Sequence[RetrievalRun]) -> list[dict[str, Any]]:
    """Each arm against the first arm of its dataset, on the same queries."""
    baseline = runs[0]
    rows = []
    for run in runs[1:]:
        try:
            difference = compare_runs(run, baseline)
        except ValueError:
            continue
        rows.append(
            {
                "arm": run.arm,
                "baseline": baseline.arm,
                "mean": difference.mean,
                "low": difference.low,
                "high": difference.high,
                "significant": difference.significant,
                "queries": len(run.queries),
            }
        )
    return rows


def render_report(
    suite_name: str,
    suite: SuiteConfig,
    runs: Sequence[RetrievalRun],
    *,
    generated_at: dt.datetime | None = None,
) -> str:
    """The report of the given runs, grouped by dataset in the order of the suite."""
    order = {arm.name: position for position, arm in enumerate(suite.retrieval)}
    ordered = sorted(runs, key=lambda run: order.get(run.arm, len(order)))
    sections: dict[str, list[RetrievalRun]] = {}
    for run in ordered:
        sections.setdefault(str(run.dataset["dataset"]), []).append(run)
    template_text = (
        resources.files("llm_testbench.eval.templates").joinpath(TEMPLATE).read_text("utf-8")
    )
    environment = Environment(autoescape=True, undefined=StrictUndefined)
    return environment.from_string(template_text).render(
        suite_name=suite_name,
        description=suite.description,
        generated_at=generated_at or dt.datetime.now(dt.UTC),
        headline=HEADLINE_METRIC,
        missing=[arm.name for arm in suite.retrieval if arm.name not in {run.arm for run in runs}],
        sections=[
            {
                "dataset": dataset,
                "describe": section[0].dataset,
                "runs": section,
                "panel": _panel(section),
                "comparisons": _comparisons(section),
            }
            for dataset, section in sections.items()
        ],
    )


def load_archived_runs(results_dir: Path, suite_name: str) -> list[RetrievalRun]:
    directory = results_dir / "runs" / suite_name
    return [load_run(path) for path in sorted(directory.glob("*.json"))]


def write_report(
    suite_name: str, suite: SuiteConfig, results_dir: Path, output: Path
) -> tuple[Path, int]:
    runs = load_archived_runs(results_dir, suite_name)
    if not runs:
        raise FileNotFoundError(
            f"no archived run for suite {suite_name!r} under {results_dir / 'runs'}: make eval"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_report(suite_name, suite, runs), encoding="utf-8")
    return output, len(runs)
