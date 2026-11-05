import pytest

from llm_testbench.config import Settings
from llm_testbench.eval.agreement import cohen_kappa
from llm_testbench.eval.loaders.squad import SquadV2Loader
from llm_testbench.eval.metrics.generation import (
    answer_f1,
    contains_answer,
    normalize_answer,
    score_answer,
)
from llm_testbench.generation.answer import REFUSAL_SENTINEL, parse_answer


def test_normalization_drops_case_punctuation_articles_and_citations() -> None:
    assert normalize_answer("The Loire rises in the Massif Central [1].") == (
        "loire rises in massif central"
    )
    assert normalize_answer("It is true [1, 2]!") == "it is true"


def test_containment_forgives_the_sentence_f1_does_not() -> None:
    answer = "The Loire rises in the Massif Central [1]."
    references = ["Massif Central", "the Massif Central"]
    assert contains_answer(answer, references)
    # 2 common tokens, 5 predicted, 2 expected: precision 0.4, recall 1.
    assert answer_f1(answer, references) == pytest.approx(2 * 0.4 * 1.0 / 1.4)
    assert answer_f1("Massif Central", references) == 1.0
    assert not contains_answer("It rises in the Alps [1].", references)
    # Whole words, in order: "1911" is not in "19110".
    assert not contains_answer("In 19110 [1].", ["1911"])


def test_each_answer_carries_only_the_metrics_that_apply(offline_settings: Settings) -> None:
    examples = {e.example_id: e for e in SquadV2Loader(offline_settings).load().examples}
    river, length = examples["q-river"], examples["q-length"]
    evidence = river.evidence("squad_v2")

    answered = parse_answer("It rises in the Massif Central [1].", evidence)
    assert score_answer(answered, answerable=True, references=river.answers) == {
        "over_refusal": 0.0,
        "contains_answer": 1.0,
        "answer_f1": pytest.approx(4 / 7),  # 2 common tokens, 5 predicted, 2 expected
        "cited": 1.0,
        "invented_citation": 0.0,
    }
    refused = parse_answer(REFUSAL_SENTINEL, evidence)
    assert score_answer(refused, answerable=True, references=river.answers) == {
        "over_refusal": 1.0,
        "contains_answer": 0.0,
        "answer_f1": 0.0,
    }
    assert score_answer(refused, answerable=False, references=length.answers) == {
        "correct_refusal": 1.0
    }
    invented = parse_answer("About 1,000 km [3].", evidence)
    assert score_answer(invented, answerable=False, references=()) == {
        "correct_refusal": 0.0,
        "cited": 0.0,
        "invented_citation": 1.0,
    }


def test_kappa_removes_the_agreement_due_to_chance() -> None:
    human = [True] * 20 + [False] * 20
    same = cohen_kappa(human, human)
    assert (same.observed, same.kappa) == (1.0, pytest.approx(1.0))
    # 30 agreements out of 40 with balanced labels: observed 0.75, expected 0.5.
    judge = [True] * 15 + [False] * 5 + [False] * 15 + [True] * 5
    partial = cohen_kappa(human, judge)
    assert partial.observed == pytest.approx(0.75)
    assert partial.kappa == pytest.approx(0.5)
    assert (partial.both_yes, partial.both_no, partial.first_only, partial.second_only) == (
        15,
        15,
        5,
        5,
    )


def test_a_judge_that_says_yes_to_everything_has_kappa_zero() -> None:
    human = [True] * 45 + [False] * 5
    lazy = cohen_kappa(human, [True] * 50)
    assert lazy.observed == pytest.approx(0.9)  # "90% agreement"
    assert lazy.kappa == pytest.approx(0.0)  # and it judged nothing
    assert cohen_kappa([True] * 5, [True] * 5).kappa is None
    with pytest.raises(ValueError, match="same items"):
        cohen_kappa([True], [True, False])
