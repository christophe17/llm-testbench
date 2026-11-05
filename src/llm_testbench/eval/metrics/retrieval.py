"""Retrieval metrics: recall@k, precision@k, MRR@k, nDCG@k.

Retrieval is judged before any text is generated: a ranking of document ids against the
relevance judgments (qrels) of one query. Nothing here knows what a model, an index or a
chunk is, and that is the point of keeping these metrics apart from the generation ones
(phase 2.1): when an answer is wrong, they say whether the evidence was on the table at all.

Conventions, those of ``trec_eval`` (through ``pytrec_eval``, what BEIR and ``mteb`` call),
so that our numbers compare to the published ones:

- a document is *relevant* when its judgment is >= 1; an unjudged document counts as 0;
- recall@k divides by the number of relevant documents, precision@k by ``k``, even when
  fewer than ``k`` documents came back;
- nDCG uses the **linear** gain (the judgment itself), not ``2**rel - 1``. On binary
  judgments the two formulas agree; on graded ones (NFCorpus: 0 to 2) they do not, and a
  harness on the wrong one is off by points while every check on SciFact stays green.

A metric is named ``<family>_at_<k>`` (``ndcg_at_10``), the names ``mteb`` writes in its
results: a score of ours and a score of theirs are compared key for key.
"""

import math
from collections.abc import Callable, Mapping, Sequence

Judgments = Mapping[str, int]
"""doc_id -> relevance level for ONE query (a row of the qrels)."""

DEFAULT_METRICS: tuple[str, ...] = (
    "ndcg_at_10",
    "recall_at_10",
    "recall_at_100",
    "precision_at_10",
    "mrr_at_10",
)
"""nDCG@10 is the BEIR headline metric; recall@100 is what a re-ranker (phase 3) is fed."""


def _relevant(judgments: Judgments) -> set[str]:
    return {doc_id for doc_id, level in judgments.items() if level >= 1}


def recall_at_k(ranking: Sequence[str], judgments: Judgments, k: int) -> float:
    """Share of the relevant documents found in the first ``k``: did we miss evidence?"""
    relevant = _relevant(judgments)
    if not relevant:
        return 0.0
    return len(relevant.intersection(ranking[:k])) / len(relevant)


def precision_at_k(ranking: Sequence[str], judgments: Judgments, k: int) -> float:
    """Share of the first ``k`` that is relevant: how much noise reaches the generator."""
    return len(_relevant(judgments).intersection(ranking[:k])) / k


def reciprocal_rank_at_k(ranking: Sequence[str], judgments: Judgments, k: int) -> float:
    """1 / rank of the first relevant document in the first ``k``, 0 if there is none.
    Averaged over the queries, it is the MRR: how far a reader scrolls before a hit."""
    relevant = _relevant(judgments)
    for rank, doc_id in enumerate(ranking[:k], start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranking: Sequence[str], judgments: Judgments, k: int) -> float:
    """Normalized discounted cumulative gain.

    Each document of the first ``k`` earns its judgment divided by ``log2(rank + 1)``: a
    relevant document at rank 1 earns 1, at rank 3 half of that. The sum (DCG) is divided
    by the best sum this query allows (IDCG: its judged documents in ideal order), so 1.0
    means "the best ranking possible", whatever the number of relevant documents.
    """
    dcg = sum(
        judgments.get(doc_id, 0) / math.log2(rank + 1)
        for rank, doc_id in enumerate(ranking[:k], start=1)
    )
    ideal = sorted((level for level in judgments.values() if level > 0), reverse=True)[:k]
    idcg = sum(level / math.log2(rank + 1) for rank, level in enumerate(ideal, start=1))
    return dcg / idcg if idcg else 0.0


_FAMILIES: dict[str, Callable[[Sequence[str], Judgments, int], float]] = {
    "ndcg": ndcg_at_k,
    "recall": recall_at_k,
    "precision": precision_at_k,
    "mrr": reciprocal_rank_at_k,
}


def _parse(metric: str) -> tuple[Callable[[Sequence[str], Judgments, int], float], int]:
    family, sep, depth = metric.partition("_at_")
    if not sep or family not in _FAMILIES or not depth.isdigit() or int(depth) < 1:
        raise ValueError(
            f"unknown metric: {metric!r} (expected <family>_at_<k>, family in {sorted(_FAMILIES)})"
        )
    return _FAMILIES[family], int(depth)


def required_depth(metrics: Sequence[str]) -> int:
    """How many documents a retriever must return for these metrics to be computable."""
    return max(_parse(metric)[1] for metric in metrics)


def evaluate_ranking(
    ranking: Sequence[str], judgments: Judgments, metrics: Sequence[str] = DEFAULT_METRICS
) -> dict[str, float]:
    """Every requested metric for one query.

    A ranking with the same document twice is refused: it is what a chunk-level search
    returns when nobody folds the chunks back into documents, and it would count one
    relevant document several times in the precision and the DCG.
    """
    if len(set(ranking)) != len(ranking):
        raise ValueError("the ranking contains the same document more than once")
    scores: dict[str, float] = {}
    for metric in metrics:
        function, k = _parse(metric)
        scores[metric] = function(ranking, judgments, k)
    return scores
