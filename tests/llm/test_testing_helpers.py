import pytest

from llm_testbench.llm.embeddings import EmbeddingRequest
from llm_testbench.llm.errors import (
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)
from llm_testbench.llm.testing import (
    Step,
    ToyEmbedder,
    anthropic_error,
    anthropic_message,
    anthropic_sse,
    scripted_anthropic_provider,
)
from llm_testbench.llm.types import CompletionRequest, DataClass, Message, ModelRef, Role


def request() -> CompletionRequest:
    return CompletionRequest(
        model=ModelRef.parse("anthropic/claude-sonnet-5"),
        messages=(Message(role=Role.USER, content="hi"),),
        data_class=DataClass.PUBLIC,
    )


async def test_scripted_provider_replays_steps_through_the_real_sdk() -> None:
    provider, script = scripted_anthropic_provider(
        [
            anthropic_error(429, "slow down", retry_after_s=3),
            Step(json_body=anthropic_message("ok", output_tokens=3)),
            Step(sse_body=anthropic_sse(["a", "b"])),
        ],
        repeat_last=False,
    )
    with pytest.raises(RateLimitedError) as info:
        await provider.complete(request())
    assert info.value.retry_after_s == 3.0

    completion = await provider.complete(request())
    assert completion.text == "ok"
    assert completion.usage.output_tokens == 3

    chunks = [c async for c in provider.stream(request())]
    assert "".join(c.text for c in chunks) == "ab"
    assert script.calls == 3
    assert script.requests[0]["model"] == "claude-sonnet-5"
    assert script.headers[0]["x-api-key"] == "scripted"


async def test_last_step_repeats_and_exceptions_are_translated() -> None:
    provider, script = scripted_anthropic_provider([Step(exception="connect")])
    for _ in range(2):
        with pytest.raises(ProviderUnavailableError):
            await provider.complete(request())
    assert script.calls == 2

    provider, _ = scripted_anthropic_provider([Step(exception="timeout")])
    with pytest.raises(ProviderTimeoutError):
        await provider.complete(request())


async def test_toy_embedder_groups_paraphrases() -> None:
    embedder = ToyEmbedder()
    a = embedder.vector("Quelle est la capitale de la France ?")
    b = embedder.vector("Capitale de la France ?")
    c = embedder.vector("Une recette de crêpes")
    assert a == b
    assert a != c
    result = await embedder.embed(
        EmbeddingRequest(
            model=ModelRef.parse("openai/toy"), texts=("x",), data_class=DataClass.PUBLIC
        )
    )
    assert result.dimensions == 3
