import pytest

from llm_testbench.llm.embeddings import EmbeddingRequest
from llm_testbench.llm.errors import (
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)
from llm_testbench.llm.testing import (
    HashingEmbedder,
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
    a = embedder.vector("What is the capital of France?")
    b = embedder.vector("Capital of France?")
    c = embedder.vector("A recipe for crepes")
    assert a == b
    assert a != c
    result = await embedder.embed(
        EmbeddingRequest(
            model=ModelRef.parse("openai/toy"), texts=("x",), data_class=DataClass.PUBLIC
        )
    )
    assert result.dimensions == 3


def test_hashing_embedder_is_lexical_deterministic_and_normalised() -> None:
    embedder = HashingEmbedder(dimensions=1024)
    a = embedder.vector("retrieval finds relevant documents")
    b = embedder.vector("documents relevant to retrieval")
    c = embedder.vector("crepes flour eggs milk")

    def dot(x: tuple[float, ...], y: tuple[float, ...]) -> float:
        return sum(p * q for p, q in zip(x, y, strict=True))

    assert dot(a, a) == pytest.approx(1.0)  # normalized
    assert dot(a, b) > 0.6  # three shared words out of four (collisions rare at 1,024 slots)
    assert abs(dot(a, c)) < 0.3  # no shared word
    assert a == embedder.vector("retrieval finds relevant documents")  # deterministic
    assert embedder.vector("") == tuple([0.0] * 1024)
