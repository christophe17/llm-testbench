from collections.abc import Callable
from typing import Any

from llm_testbench.eval.loaders.tatqa import build_tatqa_dataset, normalise_answer


def test_numeric_answer_keeps_its_scale(fixture_json: Callable[[str], Any]) -> None:
    ds = build_tatqa_dataset("dev", fixture_json("tatqa.json"))
    arith = ds.examples[0]

    # « 400 » à l'échelle « thousand » : l'échelle fait partie de la vérité.
    assert arith.answers == ["400"]
    assert arith.scale == "thousand"
    assert arith.derivation == "1200 - 800"
    assert arith.answer_type == "arithmetic"


def test_paragraphs_are_ordered_and_cells_stringified(fixture_json: Callable[[str], Any]) -> None:
    ds = build_tatqa_dataset("dev", fixture_json("tatqa.json"))
    ex = ds.examples[0]

    # Les paragraphes arrivent désordonnés dans le JSON brut : tri par `order`.
    assert ex.paragraphs == [
        "Revenue grew 20% year over year.",
        "Costs decreased thanks to efficiencies.",
    ]
    # Les cellules numériques du tableau brut sont normalisées en chaînes.
    assert ex.table[2] == ["Costs", "800", "700"]


def test_multi_span_answer_stays_a_list(fixture_json: Callable[[str], Any]) -> None:
    ds = build_tatqa_dataset("dev", fixture_json("tatqa.json"))

    assert ds.examples[1].answers == ["Revenue", "Costs"]


def test_normalise_answer_flattens_scalars() -> None:
    assert normalise_answer(42) == ["42"]
    assert normalise_answer("text") == ["text"]
    assert normalise_answer([1, "b"]) == ["1", "b"]
