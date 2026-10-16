import pytest
from pydantic import BaseModel, Field

from llm_testbench.llm.errors import StructuredOutputError
from llm_testbench.llm.prompts import PromptRegistry
from llm_testbench.llm.structured import StructuredOutputs, extract_json
from llm_testbench.llm.types import CompletionRequest, DataClass, Message, ModelRef, Role
from tests.llm.conftest import ClientFactory
from tests.llm.fakes import FakeProvider, make_completion


class Answer(BaseModel):
    city: str
    confidence: float = Field(ge=0.0, le=1.0)


def request() -> CompletionRequest:
    return CompletionRequest(
        model=ModelRef.parse("anthropic/claude-sonnet-5"),
        messages=(
            Message(role=Role.SYSTEM, content="Sois précis."),
            Message(role=Role.USER, content="Capitale de la France ?"),
        ),
        data_class=DataClass.PUBLIC,
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": 1}', '{"a": 1}'),
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('Voici la réponse : {"a": 1}. Voilà.', '{"a": 1}'),
        ("[1, 2]", "[1, 2]"),
        ("pas de json", "pas de json"),
    ],
)
def test_extract_json(text: str, expected: str) -> None:
    assert extract_json(text) == expected


def test_native_backend_gets_the_schema_and_an_untouched_system(
    make_client: ClientFactory,
) -> None:
    client, _ = make_client()
    prepared = StructuredOutputs(client, PromptRegistry.from_settings()).prepare(request(), Answer)
    assert prepared.json_schema == Answer.model_json_schema()
    assert prepared.system == "Sois précis."


def test_prompt_backend_gets_the_instruction_in_the_system_prompt(
    make_client: ClientFactory,
) -> None:
    client, _ = make_client(FakeProvider(native_json_schema=False))
    prepared = StructuredOutputs(client, PromptRegistry.from_settings()).prepare(request(), Answer)
    assert prepared.json_schema == Answer.model_json_schema()
    assert prepared.system is not None
    assert prepared.system.startswith("Sois précis.")
    assert "Schéma JSON attendu" in prepared.system
    assert '"confidence"' in prepared.system
    assert [m.role for m in prepared.turns] == [Role.USER]


async def test_invalid_output_is_repaired_with_the_validation_error(
    make_client: ClientFactory,
) -> None:
    provider = FakeProvider(
        script=[
            make_completion('{"city": "Paris", "confidence": 2}'),
            make_completion('```json\n{"city": "Paris", "confidence": 0.9}\n```'),
        ]
    )
    client, fake = make_client(provider)
    structured = StructuredOutputs(client, PromptRegistry.from_settings(), max_repairs=2)

    result = await structured.complete(request(), Answer)

    assert result.value == Answer(city="Paris", confidence=0.9)
    assert result.attempts == 2
    assert len(result.repairs) == 1
    assert "confidence" in result.repairs[0]
    second_call = fake.calls[1]
    assert second_call.messages[-2].role is Role.ASSISTANT
    assert second_call.messages[-2].content == '{"city": "Paris", "confidence": 2}'
    assert second_call.messages[-1].role is Role.USER
    assert "Erreur de validation" in second_call.messages[-1].content
    assert "confidence" in second_call.messages[-1].content


async def test_repairs_are_bounded_and_the_raw_text_is_kept(make_client: ClientFactory) -> None:
    provider = FakeProvider(script=[make_completion("pas du json"), make_completion("{}")])
    client, fake = make_client(provider)
    structured = StructuredOutputs(client, PromptRegistry.from_settings(), max_repairs=1)
    with pytest.raises(StructuredOutputError, match="2 tentative") as info:
        await structured.complete(request(), Answer)
    assert info.value.attempts == 2
    assert info.value.raw_text == "{}"
    assert "city" in info.value.last_error
    assert len(fake.calls) == 2
