import pytest

from llm_testbench.generation.answer import (
    REFUSAL_SENTINEL,
    AnswerBuilder,
    is_refusal,
    parse_answer,
    render_context,
)
from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.prompts import PromptRegistry
from llm_testbench.llm.types import ModelRef
from llm_testbench.sources.types import Evidence, Provenance


def evidence(n: int) -> list[Evidence]:
    return [
        Evidence(
            text=f"texte {i}",
            score=1.0 - i / 10,
            rank=i,
            provenance=Provenance(
                source_key="docs:t", document_id=f"d{i}", locator=f"section {i}", title=f"T{i}"
            ),
        )
        for i in range(1, n + 1)
    ]


def test_render_context_numbers_evidence_with_its_provenance() -> None:
    rendered = render_context(evidence(2))
    assert rendered == (
        "[1] docs:t › T1 › section 1\ntexte 1\n\n[2] docs:t › T2 › section 2\ntexte 2"
    )
    assert render_context([]) == "(aucun extrait)"


def test_parse_answer_maps_citations_in_order_and_flags_unknown_numbers() -> None:
    answer = parse_answer("Paris [2]. Encore Paris [2], et [1, 3] puis [7].", evidence(3))
    assert not answer.refused
    assert answer.cited_indexes == (2, 1, 3)
    assert answer.citations[0].provenance.document_id == "d2"
    assert answer.unknown_indexes == (7,)


@pytest.mark.parametrize(
    "text",
    [
        REFUSAL_SENTINEL,
        "  je ne peux pas repondre a cette question a partir des documents fournis  ",
        "JE NE PEUX PAS RÉPONDRE À CETTE QUESTION À PARTIR DES DOCUMENTS FOURNIS !",
    ],
)
def test_refusal_is_recognised_loosely_but_only_as_the_whole_answer(text: str) -> None:
    assert is_refusal(text)
    parsed = parse_answer(text, evidence(1))
    assert parsed.refused
    assert parsed.citations == ()


def test_a_refusal_buried_in_an_answer_is_not_a_refusal() -> None:
    assert not is_refusal(f"Paris [1]. {REFUSAL_SENTINEL}")


def test_build_request_puts_context_and_sentinel_in_the_system_prompt() -> None:
    builder = AnswerBuilder(PromptRegistry.from_settings())
    request = builder.build_request(
        "Quelle capitale ?",
        evidence(2),
        model=ModelRef.parse("anthropic/claude-sonnet-5"),
        data_class=DataClass.PUBLIC,
    )
    assert request.system is not None
    assert "[1] docs:t › T1 › section 1\ntexte 1" in request.system
    assert REFUSAL_SENTINEL in request.system
    assert request.turns[0].content == "Quelle capitale ?"
    assert request.metadata["prompt.name"] == "chat_answer"
    assert request.metadata["prompt.version"] == "1"
    assert len(request.metadata["prompt.sha256"]) == 64
