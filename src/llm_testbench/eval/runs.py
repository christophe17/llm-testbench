"""What a run of the harness leaves behind: a record that explains its own numbers.

A score alone is a number nobody can check three weeks later. A :class:`RetrievalRun`
carries what produced it (the dataset as loaded, the retriever as configured, the index it
read, the commit of the code), what it measured (each metric with its confidence interval,
latency, cost), the per-query scores (so that two runs can be compared query by query,
:func:`llm_testbench.eval.stats.paired_bootstrap`), and the published scores it is compared
to, with their source.

A run on a truncated dataset, on fixtures or on simulated embeddings says so
(``publishable`` is false): it checks the mechanics, it is never archived and never quoted.
"""

import datetime as dt
import subprocess
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from llm_testbench.retrieval.types import Description

HEADLINE_METRIC = "ndcg_at_10"


class MetricSummary(BaseModel):
    """Mean over the queries, with its bootstrap interval."""

    model_config = ConfigDict(frozen=True)

    mean: float
    low: float
    high: float


class Reference(BaseModel):
    """A score someone else published, or that we measured with another tool."""

    model_config = ConfigDict(frozen=True)

    label: str
    value: float
    source: str
    metric: str = HEADLINE_METRIC


class IndexBuild(BaseModel):
    """What it took to have the index this run read (zero when it was already there)."""

    model_config = ConfigDict(frozen=True)

    index_key: str
    documents: int
    chunks: int
    chunks_embedded: int = 0
    embedding_tokens: int = 0
    cost_usd: float | None = 0.0
    seconds: float = Field(ge=0)


class QueryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    query_id: str
    metrics: dict[str, float]
    ranking: tuple[str, ...]
    """The first documents returned (ids), kept to look at a failure, not to recompute."""
    latency_ms: float


class RetrievalRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    created_at: dt.datetime
    suite: str
    arm: str
    dataset: dict[str, int | str | bool]
    retriever: Description
    index: IndexBuild | None = None
    sample_mode: bool = False
    """True when the run did not see the real thing: fixtures instead of the dataset, or a
    simulator instead of the embedding model."""
    depth: int
    """Documents asked from the retriever per query (the deepest ``k`` of the metrics)."""
    metrics: dict[str, MetricSummary]
    latency_ms: dict[str, float]
    """``mean``, ``p50``, ``p95`` of the per-query wall-clock time."""
    timings_ms: dict[str, float]
    """Mean time per step (``embed``, ``search``), as reported by the retriever."""
    cost_usd: float | None
    """Query-time cost of the whole run; ``None`` as soon as one call has an unknown price."""
    duration_s: float
    queries_skipped: int = 0
    """Queries without any relevant document: no metric is defined on them."""
    references: tuple[Reference, ...] = ()
    git_sha: str | None = None
    git_dirty: bool | None = None
    queries: tuple[QueryResult, ...]

    @property
    def publishable(self) -> bool:
        return not self.dataset.get("sampled", False) and not self.sample_mode

    def per_query(self, metric: str) -> dict[str, float]:
        return {result.query_id: result.metrics[metric] for result in self.queries}

    def gap(self, reference: Reference) -> float:
        """Ours minus theirs. A large gap is a bug to find, not a result (phase 2.2)."""
        return self.metrics[reference.metric].mean - reference.value


def git_state(root: Path | None = None) -> tuple[str | None, bool | None]:
    """(short commit, uncommitted changes?) of the code that ran; (None, None) outside a
    repository (the container image)."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None, None
    return sha or None, bool(status)


def format_runs(runs: Sequence[RetrievalRun]) -> str:
    """The comparison table of a suite, as the CLI and the notebooks print it."""
    header = (
        f"{'arm':<30} {'dataset':<14} {'nDCG@10':>8} {'95% interval':>15} {'R@100':>6} "
        f"{'MRR@10':>7} {'p50 ms':>7} {'p95 ms':>7} {'cost':>8}  reference (gap)"
    )
    rows = [header]
    for run in runs:
        headline = run.metrics[HEADLINE_METRIC]
        recall = run.metrics.get("recall_at_100")
        mrr = run.metrics.get("mrr_at_10")
        cost = "unknown" if run.cost_usd is None else f"${run.cost_usd:.4f}"
        references = "; ".join(
            f"{reference.value:.3f} {reference.label} ({run.gap(reference):+.3f})"
            for reference in run.references
            if reference.metric in run.metrics
        )
        flag = "" if run.publishable else "  [NOT PUBLISHABLE: sample]"
        rows.append(
            f"{run.arm:<30} {run.dataset['dataset']!s:<14} {headline.mean:>8.3f} "
            f"{f'[{headline.low:.3f}, {headline.high:.3f}]':>15} "
            f"{f'{recall.mean:.3f}' if recall else '—':>6} "
            f"{f'{mrr.mean:.3f}' if mrr else '—':>7} "
            f"{run.latency_ms['p50']:>7.1f} {run.latency_ms['p95']:>7.1f} {cost:>8}  "
            f"{references or '—'}{flag}"
        )
    return "\n".join(rows)


def save_run(run: RetrievalRun, results_dir: Path) -> Path:
    """Archive a run as ``<results_dir>/runs/<suite>/<arm>.json``: one file per arm, the
    latest full run, versioned with the code. Its history is the file's git history (and the
    ``eval_runs`` table, while the database lives)."""
    if not run.publishable:
        raise ValueError(f"run {run.run_id} is not publishable (sample mode): not archived")
    path = results_dir / "runs" / run.suite / f"{run.arm}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(run.model_dump_json(indent=1) + "\n", encoding="utf-8")
    return path


def load_run(path: Path) -> RetrievalRun:
    return RetrievalRun.model_validate_json(path.read_text(encoding="utf-8"))
