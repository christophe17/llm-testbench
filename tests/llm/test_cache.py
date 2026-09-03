import pytest

from llm_testbench.llm.cache import (
    InMemoryCache,
    cosine_similarity,
    exact_key,
    semantic_namespace,
)
from llm_testbench.llm.types import (
    Completion,
    CompletionRequest,
    DataClass,
    FinishReason,
    Message,
    ModelRef,
    Role,
    Usage,
)


def request(
    *, user: str = "Bonjour ?", system: str | None = "Sois bref.", **overrides: object
) -> CompletionRequest:
    messages: list[Message] = []
    if system is not None:
        messages.append(Message(role=Role.SYSTEM, content=system))
    messages.append(Message(role=Role.USER, content=user))
    fields: dict[str, object] = {
        "model": ModelRef.parse("anthropic/claude-sonnet-5"),
        "messages": tuple(messages),
        "data_class": DataClass.PUBLIC,
    }
    fields.update(overrides)
    return CompletionRequest.model_validate(fields)


def completion(text: str) -> Completion:
    return Completion(
        text=text,
        model="m",
        backend="anthropic",
        usage=Usage(input_tokens=1, output_tokens=1),
        finish_reason=FinishReason.STOP,
    )


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_exact_key_covers_everything_that_changes_the_answer_and_nothing_else() -> None:
    base = exact_key(request())
    assert base == exact_key(request())
    assert base == exact_key(request(metadata={"prompt.name": "x"}))  # la trace n'entre pas
    assert base == exact_key(request(data_class=DataClass.INTERNAL))
    assert base != exact_key(request(user="Bonjour !"))
    assert base != exact_key(request(system="Sois long."))
    assert base != exact_key(request(max_output_tokens=2))
    assert base != exact_key(request(temperature=0.5))
    assert base != exact_key(request(model=ModelRef.parse("openai/gpt-5.6-luna")))
    assert base != exact_key(request(json_schema={"type": "object"}))


def test_semantic_namespace_freezes_everything_but_the_user_message() -> None:
    namespace = semantic_namespace(request())
    assert namespace is not None
    assert namespace == semantic_namespace(request(user="Une autre question"))
    assert namespace != semantic_namespace(request(system="Autre system"))
    assert namespace != semantic_namespace(request(max_output_tokens=2))
    multi_turn = request().with_messages(
        (
            Message(role=Role.USER, content="a"),
            Message(role=Role.ASSISTANT, content="b"),
            Message(role=Role.USER, content="c"),
        )
    )
    assert semantic_namespace(multi_turn) is None


def test_cosine_similarity() -> None:
    assert cosine_similarity((1.0, 0.0), (1.0, 0.0)) == pytest.approx(1.0)
    assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)
    assert cosine_similarity((0.0, 0.0), (1.0, 0.0)) == 0.0
    with pytest.raises(ValueError, match="dimensions"):
        cosine_similarity((1.0,), (1.0, 0.0))


async def test_in_memory_exact_get_put_and_ttl() -> None:
    clock = FakeClock()
    cache = InMemoryCache(ttl_s=10, clock=clock)
    assert await cache.get("k") is None
    await cache.put("k", completion("v"))
    assert (await cache.get("k")) == completion("v")
    clock.now = 10
    assert await cache.get("k") is None
    assert len(cache) == 0


async def test_in_memory_semantic_lookup_respects_threshold_and_namespace() -> None:
    cache = InMemoryCache()
    await cache.put("k1", completion("réponse 1"))
    await cache.put("k2", completion("réponse 2"))
    await cache.put_vector("ns", (1.0, 0.0), "k1")
    await cache.put_vector("ns", (0.8, 0.6), "k2")

    hit = await cache.find_similar("ns", (0.9, 0.1), min_similarity=0.9)
    assert hit is not None
    assert hit[0].text == "réponse 1"
    assert hit[1] == pytest.approx(0.9939, abs=1e-3)

    assert await cache.find_similar("ns", (0.0, 1.0), min_similarity=0.9) is None
    assert await cache.find_similar("other", (1.0, 0.0), min_similarity=0.5) is None


async def test_in_memory_semantic_hit_on_expired_entry_is_a_miss() -> None:
    clock = FakeClock()
    cache = InMemoryCache(ttl_s=5, clock=clock)
    await cache.put("k", completion("v"))
    await cache.put_vector("ns", (1.0, 0.0), "k")
    clock.now = 6
    assert await cache.find_similar("ns", (1.0, 0.0), min_similarity=0.99) is None
