from collections.abc import Callable
from typing import Any

from llm_testbench.eval.loaders.squad_v2 import build_qa_dataset


def test_answerable_example(fixture_json: Callable[[str], Any]) -> None:
    ds = build_qa_dataset("validation", fixture_json("squad_v2.json"))
    ex = ds.examples[0]

    assert ex.is_answerable
    # Dédoublonnage en préservant l'ordre : les annotateurs répètent souvent la même réponse.
    assert ex.answers == ["Paris", "paris"]
    assert len(ex.contexts) == 1
    assert ex.contexts[0].text.startswith("Paris is")


def test_unanswerable_example(fixture_json: Callable[[str], Any]) -> None:
    ds = build_qa_dataset("validation", fixture_json("squad_v2.json"))
    ex = ds.examples[1]

    # Le marqueur SQuAD 2.0 est implicite : answers vide <=> non répondable.
    assert not ex.is_answerable
    assert ex.answers == []
