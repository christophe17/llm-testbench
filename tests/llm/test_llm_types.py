import pytest
from pydantic import ValidationError

from llm_testbench.llm import CompletionRequest, DataClass, Message, ModelRef, Role, Usage


def test_model_ref_parse_splits_on_first_slash_only() -> None:
    ref = ModelRef.parse("openrouter/mistralai/mistral-large")
    assert ref.backend == "openrouter"
    assert ref.model == "mistralai/mistral-large"
    assert str(ref) == "openrouter/mistralai/mistral-large"


@pytest.mark.parametrize("bad", ["claude-sonnet-5", "/x", "anthropic/", ""])
def test_model_ref_parse_rejects_malformed(bad: str) -> None:
    with pytest.raises(ValueError, match="backend/modèle"):
        ModelRef.parse(bad)


def test_completion_request_requires_an_explicit_data_class() -> None:
    with pytest.raises(ValidationError, match="data_class"):
        CompletionRequest.model_validate(
            {
                "model": {"backend": "anthropic", "model": "claude-sonnet-5"},
                "messages": [{"role": "user", "content": "hi"}],
            }
        )


def test_completion_request_rejects_system_message_not_first() -> None:
    with pytest.raises(ValidationError, match="première position"):
        CompletionRequest(
            model=ModelRef.parse("anthropic/claude-sonnet-5"),
            messages=(
                Message(role=Role.USER, content="hi"),
                Message(role=Role.SYSTEM, content="late system"),
            ),
            data_class=DataClass.PUBLIC,
        )


def test_completion_request_splits_system_and_turns_and_is_frozen() -> None:
    request = CompletionRequest(
        model=ModelRef.parse("anthropic/claude-sonnet-5"),
        messages=(
            Message(role=Role.SYSTEM, content="be brief"),
            Message(role=Role.USER, content="hi"),
        ),
        data_class=DataClass.PUBLIC,
    )
    assert request.system == "be brief"
    assert [m.content for m in request.turns] == ["hi"]
    with pytest.raises(ValidationError):
        request.max_output_tokens = 5  # type: ignore[misc]
    derived = request.with_messages((Message(role=Role.USER, content="other"),))
    assert derived.system is None
    assert derived.model == request.model


def test_usage_totals_and_addition() -> None:
    usage = Usage(input_tokens=100, output_tokens=20, cache_read_tokens=400, cache_write_tokens=50)
    assert usage.total_input_tokens == 550
    assert usage.total_tokens == 570
    total = usage + Usage(input_tokens=1, output_tokens=1)
    assert (total.input_tokens, total.output_tokens, total.cache_read_tokens) == (101, 21, 400)
