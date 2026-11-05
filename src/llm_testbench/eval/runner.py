"""The retrieval runner: a dataset, a retriever, a record.

For each query of the dataset: ask the retriever for a ranking, score it against the
judgments, time it. Then summarize: each metric becomes a mean with a bootstrap interval,
latency becomes percentiles, cost a sum. The runner knows neither BM25 nor pgvector: it
sees a :class:`~llm_testbench.retrieval.types.Retriever`, which is what lets one table
compare a lexical index, a vector index and whatever phase 3 adds.
"""

import datetime as dt
import time
from collections.abc import Sequence

import numpy as np

from llm_testbench.eval.metrics import DEFAULT_METRICS, evaluate_ranking, required_depth
from llm_testbench.eval.runs import (
    IndexBuild,
    MetricSummary,
    QueryResult,
    Reference,
    RetrievalRun,
    git_state,
)
from llm_testbench.eval.stats import DEFAULT_RESAMPLES, bootstrap_mean
from llm_testbench.eval.types import RetrievalDataset
from llm_testbench.retrieval.types import Retriever

KEPT_RANKING = 10


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
