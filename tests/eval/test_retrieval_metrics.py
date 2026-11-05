"""Retrieval metrics against values computed by hand, then against ``pytrec_eval``."""

import math
import random

import pytest

from llm_testbench.eval.metrics import (
    DEFAULT_METRICS,
    evaluate_ranking,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank_at_k,
    required_depth,
)

# One query, three relevant documents out of five judged; "x*" are unjudged.
JUDGMENTS = {"a": 1, "b": 1, "c": 1, "d": 0, "e": 0}
RANKING = ["x1", "a", "d", "b", "x2", "x3", "x4", "x5", "x6", "x7", "c"]


def test_recall_divides_by_the_number_of_relevant_documents() -> None:
    assert recall_at_k(RANKING, JUDGMENTS, 1) == 0.0
    assert recall_at_k(RANKING, JUDGMENTS, 4) == pytest.approx(2 / 3)
    assert recall_at_k(RANKING, JUDGMENTS, 100) == 1.0


def test_precision_divides_by_k_even_when_fewer_documents_came_back() -> None:
    assert precision_at_k(RANKING, JUDGMENTS, 4) == pytest.approx(2 / 4)
    assert precision_at_k(["a"], JUDGMENTS, 10) == pytest.approx(1 / 10)


def test_reciprocal_rank_stops_at_the_first_relevant_document() -> None:
    assert reciprocal_rank_at_k(RANKING, JUDGMENTS, 10) == pytest.approx(1 / 2)
    assert reciprocal_rank_at_k(RANKING, JUDGMENTS, 1) == 0.0


def test_ndcg_on_binary_judgments() -> None:
    # Relevant at ranks 2 and 4; the ideal ranking puts the three relevant at ranks 1-3.
    dcg = 1 / math.log2(3) + 1 / math.log2(5)
    idcg = 1 / math.log2(2) + 1 / math.log2(3) + 1 / math.log2(4)
    assert ndcg_at_k(RANKING, JUDGMENTS, 10) == pytest.approx(dcg / idcg)


def test_ndcg_uses_the_linear_gain_on_graded_judgments() -> None:
    graded = {"a": 2, "b": 1}
    # "b" (1) ahead of "a" (2): linear gain 1/log2(2) + 2/log2(3), ideal 2/log2(2) + 1/log2(3).
    linear = (1 + 2 / math.log2(3)) / (2 + 1 / math.log2(3))
    exponential = (1 + 3 / math.log2(3)) / (3 + 1 / math.log2(3))
    assert ndcg_at_k(["b", "a"], graded, 10) == pytest.approx(linear)
    assert linear != pytest.approx(exponential)


def test_a_perfect_ranking_scores_one_and_an_empty_one_zero() -> None:
    assert ndcg_at_k(["a", "b", "c"], JUDGMENTS, 10) == pytest.approx(1.0)
    assert evaluate_ranking([], JUDGMENTS) == dict.fromkeys(DEFAULT_METRICS, 0.0)


def test_a_query_without_relevant_document_scores_zero() -> None:
    assert evaluate_ranking(["d", "e"], {"d": 0, "e": 0}) == dict.fromkeys(DEFAULT_METRICS, 0.0)


def test_evaluate_ranking_names_and_depth() -> None:
    scores = evaluate_ranking(RANKING, JUDGMENTS, ["recall_at_4", "mrr_at_10"])
    assert scores == {"recall_at_4": pytest.approx(2 / 3), "mrr_at_10": pytest.approx(1 / 2)}
    assert required_depth(DEFAULT_METRICS) == 100


def test_a_duplicated_document_is_refused() -> None:
    with pytest.raises(ValueError, match="more than once"):
        evaluate_ranking(["a", "a"], JUDGMENTS)


@pytest.mark.parametrize("metric", ["ndcg", "ndcg_at_0", "map_at_10", "ndcg_at_ten"])
def test_unknown_metric_is_refused(metric: str) -> None:
    with pytest.raises(ValueError, match="unknown metric"):
        evaluate_ranking(RANKING, JUDGMENTS, [metric])


def test_agreement_with_pytrec_eval_on_random_rankings() -> None:
    """The reference implementation behind BEIR and ``mteb``; installed with the bench group."""
    pytrec_eval = pytest.importorskip("pytrec_eval")
    rng = random.Random(7)
    doc_ids = [f"d{i}" for i in range(60)]
    qrels: dict[str, dict[str, int]] = {}
    run: dict[str, dict[str, float]] = {}
    rankings: dict[str, list[str]] = {}
    for q in range(40):
        judged = rng.sample(doc_ids, 12)
        qrels[f"q{q}"] = {doc_id: rng.choice([0, 1, 1, 2]) for doc_id in judged}
        ranking = rng.sample(doc_ids, 30)
        rankings[f"q{q}"] = ranking
        # Strictly decreasing scores: trec_eval re-sorts by score, ties would reorder.
        run[f"q{q}"] = {doc_id: float(len(ranking) - rank) for rank, doc_id in enumerate(ranking)}
    evaluator = pytrec_eval.RelevanceEvaluator(qrels, {"ndcg_cut.10", "recall.10", "P.10"})
    expected = evaluator.evaluate(run)
    for query_id, ranking in rankings.items():
        if not any(level > 0 for level in qrels[query_id].values()):
            continue
        ours = evaluate_ranking(
            ranking, qrels[query_id], ["ndcg_at_10", "recall_at_10", "precision_at_10"]
        )
        assert ours["ndcg_at_10"] == pytest.approx(expected[query_id]["ndcg_cut_10"], abs=1e-9)
        assert ours["recall_at_10"] == pytest.approx(expected[query_id]["recall_10"], abs=1e-9)
        assert ours["precision_at_10"] == pytest.approx(expected[query_id]["P_10"], abs=1e-9)
