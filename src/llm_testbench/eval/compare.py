"""Two runs, query by query: is the difference real?

Both runs must have seen the same queries. The comparison resamples the per-query
differences (:func:`llm_testbench.eval.stats.paired_bootstrap`): when the interval of the
difference excludes zero, the candidate is better (or worse) beyond the luck of the sample.
"""

from llm_testbench.eval.runs import HEADLINE_METRIC, RetrievalRun
from llm_testbench.eval.stats import DEFAULT_RESAMPLES, PairedDifference, paired_bootstrap


def compare_runs(
    candidate: RetrievalRun,
    baseline: RetrievalRun,
    metric: str = HEADLINE_METRIC,
    *,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = 0,
) -> PairedDifference:
    ours, theirs = candidate.per_query(metric), baseline.per_query(metric)
    if ours.keys() != theirs.keys():
        raise ValueError(
            f"{candidate.arm} and {baseline.arm} did not see the same queries: "
            "a paired comparison needs one score per query on both sides"
        )
    query_ids = sorted(ours)
    return paired_bootstrap(
        [ours[query_id] for query_id in query_ids],
        [theirs[query_id] for query_id in query_ids],
        resamples=resamples,
        seed=seed,
    )


def describe_difference(difference: PairedDifference, metric: str = HEADLINE_METRIC) -> str:
    verdict = (
        "no significant difference"
        if not difference.significant
        else ("significantly better" if difference.mean > 0 else "significantly worse")
    )
    return (
        f"Δ {metric} = {difference.mean:+.4f} "
        f"[{difference.low:+.4f}, {difference.high:+.4f}] — {verdict}"
    )
