from collections.abc import Callable
from typing import Any

from llm_testbench.eval.loaders.hotpotqa import build_qa_dataset


def test_contexts_include_distractors(fixture_json: Callable[[str], Any]) -> None:
    ds = build_qa_dataset("validation", fixture_json("hotpotqa.json"))
    ex = ds.examples[0]

    assert len(ex.contexts) == 3
    # Les phrases d'un paragraphe sont recollées telles quelles (HotpotQA inclut les espaces).
    assert ex.contexts[0].text == (
        "The inventor of X studied at University Y. They were born in 1900."
    )


def test_supporting_titles_are_deduplicated(fixture_json: Callable[[str], Any]) -> None:
    ds = build_qa_dataset("validation", fixture_json("hotpotqa.json"))
    ex = ds.examples[0]

    # supporting_facts liste (titre, phrase) : un titre peut apparaître plusieurs fois.
    assert ex.supporting_doc_ids == ["Inventor of X", "University Y"]
    assert ex.metadata == {"level": "medium", "type": "bridge"}
    assert ex.is_answerable
