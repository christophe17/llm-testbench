from collections.abc import Callable
from typing import Any

from llm_testbench.eval.loaders.qasper import build_papers


def test_full_document_is_preserved(fixture_json: Callable[[str], Any]) -> None:
    paper = build_papers(fixture_json("qasper.json"))[0]

    assert paper.title == "A Study of Things"
    assert [s.section_name for s in paper.sections] == ["Introduction", "Method"]
    # Le document n'est PAS pré-découpé : c'est ce qui permettra le duel de chunking.
    assert paper.sections[0].paragraphs == ["Things are important.", "Prior work ignored things."]


def test_answers_and_evidence_are_aggregated(fixture_json: Callable[[str], Any]) -> None:
    paper = build_papers(fixture_json("qasper.json"))[0]
    q1 = paper.questions[0]

    assert q1.is_answerable
    # Agrégation des annotations multiples, dédoublonnée, ordre préservé.
    assert q1.answers == ["with a ruler", "using a ruler"]
    assert q1.evidence == ["We measure things with a ruler.", "Things are important."]


def test_unanswerable_requires_all_annotations(fixture_json: Callable[[str], Any]) -> None:
    paper = build_papers(fixture_json("qasper.json"))[0]
    q2 = paper.questions[1]

    # Convention : non répondable seulement si TOUTES les annotations le disent.
    assert not q2.is_answerable
    assert q2.answers == []
