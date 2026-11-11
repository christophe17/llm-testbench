"""The retrieval runner: a dataset, a retriever, a record.

For each query of the dataset: ask the retriever for a ranking, score it against the
judgments, time it. Then summarize: each metric becomes a mean with a bootstrap interval,
latency becomes percentiles, cost a sum. The runner knows neither BM25 nor pgvector: it
sees a :class:`~llm_testbench.retrieval.types.Retriever`, which is what lets one table
compare a lexical index, a vector index and whatever phase 3 adds.

What the run leaves behind is a record that explains its own numbers. A score alone is a
number nobody can check three weeks later. A :class:`RetrievalRun` carries what produced it
(the dataset as loaded, the retriever as configured, the index it read, the commit of the
code), what it measured (each metric with its confidence interval, latency, cost), the
per-query scores (so that two runs can be compared query by query,
:func:`llm_testbench.eval.stats.paired_bootstrap`), and the published scores it is compared
to, with their source.

A run on a truncated dataset, on fixtures or on simulated embeddings says so
(``publishable`` is false): it checks the mechanics, it is never archived and never quoted.

This module is the retrieval twin of ``eval/generation.py``: the record, the function that
produces it, its archive. What both kinds of run share is in ``eval/runs.py``.
"""

import datetime as dt
import json
import time
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict

from llm_testbench.eval.metrics import DEFAULT_METRICS, evaluate_ranking, required_depth
from llm_testbench.eval.runs import IndexBuild, git_state
from llm_testbench.eval.stats import DEFAULT_RESAMPLES, bootstrap_mean
from llm_testbench.eval.types import RetrievalDataset
from llm_testbench.retrieval.types import Description, Retriever

HEADLINE_METRIC = "ndcg_at_10"
KEPT_RANKING = 10


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


async def run_retrieval(
    dataset: RetrievalDataset,
    retriever: Retriever,
    *,
    suite: str,
    arm: str,
    metrics: Sequence[str] = DEFAULT_METRICS,
    references: Sequence[Reference] = (),
    index: IndexBuild | None = None,
    sample_mode: bool = False,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = 0,
) -> RetrievalRun:
    depth = required_depth(metrics)
    created_at = dt.datetime.now(dt.UTC)
    started = time.perf_counter()

    # First call outside the measurement: it pays for what is paid once (loading a model,
    # opening a connection), which is not the latency of a query.
    await retriever.retrieve(dataset.queries[0].text, k=depth)

    results: list[QueryResult] = []
    step_totals: dict[str, float] = {}
    cost: float | None = 0.0
    skipped = 0
    for query in dataset.queries:
        judgments = dataset.qrels[query.query_id]
        if not any(level >= 1 for level in judgments.values()):
            skipped += 1
            continue
        query_started = time.perf_counter()
        retrieval = await retriever.retrieve(query.text, k=depth)
        latency_ms = (time.perf_counter() - query_started) * 1000.0
        ranking = retrieval.doc_ids
        results.append(
            QueryResult(
                query_id=query.query_id,
                metrics=evaluate_ranking(ranking, judgments, metrics),
                ranking=tuple(ranking[:KEPT_RANKING]),
                latency_ms=latency_ms,
            )
        )
        for step, elapsed in retrieval.timings_ms.items():
            step_totals[step] = step_totals.get(step, 0.0) + elapsed
        cost = None if cost is None or retrieval.cost_usd is None else cost + retrieval.cost_usd
    if not results:
        raise ValueError("no query with a relevant document: nothing to measure")

    summary: dict[str, MetricSummary] = {}
    for metric in metrics:
        interval = bootstrap_mean(
            [result.metrics[metric] for result in results], resamples=resamples, seed=seed
        )
        summary[metric] = MetricSummary(mean=interval.mean, low=interval.low, high=interval.high)
    latencies = np.asarray([result.latency_ms for result in results])
    sha, dirty = git_state()
    return RetrievalRun(
        run_id=f"{created_at:%Y%m%dT%H%M%SZ}-{suite}-{arm}",
        created_at=created_at,
        suite=suite,
        arm=arm,
        dataset=dataset.describe(),
        retriever=retriever.describe(),
        index=index,
        sample_mode=sample_mode,
        depth=depth,
        metrics=summary,
        latency_ms={
            "mean": float(latencies.mean()),
            "p50": float(np.percentile(latencies, 50)),
            "p95": float(np.percentile(latencies, 95)),
        },
        timings_ms={step: total / len(results) for step, total in step_totals.items()},
        cost_usd=cost,
        duration_s=time.perf_counter() - started,
        queries_skipped=skipped,
        references=tuple(references),
        git_sha=sha,
        git_dirty=dirty,
        queries=tuple(results),
    )


def format_retrieval_runs(runs: Sequence[RetrievalRun]) -> str:
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


def save_retrieval_run(run: RetrievalRun, results_dir: Path) -> Path:
    """Archive a run as ``<results_dir>/runs/<suite>/<arm>.json``: one file per arm, the
    latest full run, versioned with the code. Its history is the file's git history (and the
    ``eval_runs`` table, while the database lives)."""
    if not run.publishable:
        raise ValueError(f"run {run.run_id} is not publishable (sample mode): not archived")
    path = results_dir / "runs" / run.suite / f"{run.arm}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    # The summary indented, then one line per query: a rerun shows in `git diff` as the
    # numbers that moved and the queries that changed, not as six thousand lines.
    record = run.model_dump(mode="json")
    queries = record.pop("queries")
    summary = json.dumps(record, indent=1, ensure_ascii=False)
    lines = ",\n".join(
        "  " + json.dumps(query, ensure_ascii=False, separators=(",", ":")) for query in queries
    )
    path.write_text(
        summary.removesuffix("\n}") + f',\n "queries": [\n{lines}\n ]\n}}\n', encoding="utf-8"
    )
    return path


def load_retrieval_run(path: Path) -> RetrievalRun:
    return RetrievalRun.model_validate_json(path.read_text(encoding="utf-8"))
