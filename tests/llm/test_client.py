from collections.abc import AsyncIterator

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from llm_testbench.llm.budget import TokenBudget
from llm_testbench.llm.cache import InMemoryCache
from llm_testbench.llm.client import SemanticCacheConfig
from llm_testbench.llm.embeddings import EmbeddingRequest
from llm_testbench.llm.errors import (
    BudgetExceededError,
    CircuitOpenError,
    GovernanceViolation,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from llm_testbench.llm.resilience import CircuitBreaker, RetryPolicy
from llm_testbench.llm.types import (
    CompletionRequest,
    DataClass,
    FinishReason,
    Message,
    ModelRef,
    Role,
    StreamChunk,
)
from llm_testbench.obs.tracing import Bench, GenAI
from tests.llm.conftest import ClientFactory, FakeSleep, last_span
from tests.llm.fakes import FakeEmbedder, FakeProvider, make_completion

SONNET = ModelRef.parse("anthropic/claude-sonnet-5")
EMBED = ModelRef.parse("openai/text-embedding-3-small")


def request(
    user: str = "Quelle est la capitale de la France ?",
    *,
    system: str = "Réponds en un mot.",
    data_class: DataClass = DataClass.PUBLIC,
    **overrides: object,
) -> CompletionRequest:
    fields: dict[str, object] = {
        "model": SONNET,
        "messages": (
            Message(role=Role.SYSTEM, content=system),
            Message(role=Role.USER, content=user),
        ),
        "data_class": data_class,
        "metadata": {"prompt.name": "chat_answer", "prompt.version": "1", "prompt.sha256": "abc"},
    }
    fields.update(overrides)
    return CompletionRequest.model_validate(fields)


async def drain(stream: AsyncIterator[StreamChunk]) -> list[StreamChunk]:
    return [chunk async for chunk in stream]


# ------------------------------------------------------------------ chemin nominal


async def test_complete_prices_the_call_and_traces_it(
    make_client: ClientFactory, spans: InMemorySpanExporter
) -> None:
    client, fake = make_client()

    completion = await client.complete(request())

    assert completion.text == "réponse"
    assert completion.cost_usd == pytest.approx(0.002 + 0.005)  # 1 000 in + 500 out, Sonnet 5
    assert completion.attempts == 1
    assert not completion.cached
    assert len(fake.calls) == 1

    span = last_span(spans)
    assert span.name == "chat anthropic/claude-sonnet-5"
    attributes = dict(span.attributes or {})
    assert attributes[GenAI.OPERATION_NAME] == "chat"
    assert attributes[GenAI.PROVIDER_NAME] == "anthropic"
    assert attributes[GenAI.REQUEST_MODEL] == "claude-sonnet-5"
    assert attributes[GenAI.RESPONSE_MODEL] == "claude-sonnet-5"
    assert attributes[GenAI.RESPONSE_ID] == "msg_fake"
    assert attributes[GenAI.USAGE_INPUT_TOKENS] == 1_000
    assert attributes[GenAI.USAGE_OUTPUT_TOKENS] == 500
    assert attributes[GenAI.RESPONSE_FINISH_REASONS] == ("stop",)
    assert attributes[Bench.COST_USD] == pytest.approx(0.007)
    assert attributes[Bench.COST_KNOWN] is True
    assert attributes[Bench.CACHED] is False
    assert attributes[Bench.ATTEMPTS] == 1
    assert attributes[Bench.DATA_CLASS] == "public"
    assert attributes[Bench.GOVERNANCE_ALLOWED] is True
    assert attributes[Bench.INFERENCE_REGION] == "us"
    assert attributes[Bench.PROMPT_NAME] == "chat_answer"
    assert attributes[Bench.PROMPT_SHA256] == "abc"
    assert span.status.status_code is StatusCode.UNSET


async def test_unknown_model_price_yields_unknown_cost(
    make_client: ClientFactory, spans: InMemorySpanExporter
) -> None:
    client, _ = make_client(FakeProvider(script=[make_completion(model="mystery-model")]))
    completion = await client.complete(request())
    assert completion.cost_usd is None
    assert dict(last_span(spans).attributes or {})[Bench.COST_KNOWN] is False


# ------------------------------------------------------------------ refus avant l'appel


async def test_governance_refuses_before_any_provider_call(
    make_client: ClientFactory, spans: InMemorySpanExporter
) -> None:
    client, fake = make_client()
    with pytest.raises(GovernanceViolation, match="anthropic"):
        await client.complete(request(data_class=DataClass.REGULATED))
    assert fake.calls == []
    span = last_span(spans)
    attributes = dict(span.attributes or {})
    assert attributes[Bench.GOVERNANCE_ALLOWED] is False
    assert any("région" in r for r in attributes[Bench.GOVERNANCE_REASONS])  # type: ignore[union-attr]
    assert span.status.status_code is StatusCode.ERROR


async def test_budget_refuses_on_estimate_and_records_real_usage(
    make_client: ClientFactory,
) -> None:
    budget = TokenBudget(max_tokens_per_window=2_000)
    client, fake = make_client(budget=budget)
    await client.complete(request())
    assert budget.spent_in_window() == 1_500
    with pytest.raises(BudgetExceededError, match="déjà consommés"):
        await client.complete(request(max_output_tokens=600))
    assert len(fake.calls) == 1


# ------------------------------------------------------------------ pannes


async def test_retry_then_success_counts_attempts(
    make_client: ClientFactory, spans: InMemorySpanExporter, fake_sleep: FakeSleep
) -> None:
    provider = FakeProvider(
        script=[ProviderUnavailableError("503", backend="anthropic"), make_completion("ok")]
    )
    client, _ = make_client(provider)
    completion = await client.complete(request())
    assert completion.text == "ok"
    assert completion.attempts == 2
    assert len(fake_sleep.delays) == 1
    assert dict(last_span(spans).attributes or {})[Bench.ATTEMPTS] == 2


async def test_circuit_opens_after_repeated_failures_and_fails_fast(
    make_client: ClientFactory,
) -> None:
    down = ProviderUnavailableError("503", backend="anthropic")
    provider = FakeProvider(script=[down, down, down, down])
    client, fake = make_client(
        provider,
        breaker_factory=lambda backend: CircuitBreaker(
            backend=backend, failure_threshold=2, recovery_timeout_s=60
        ),
    )
    with pytest.raises(CircuitOpenError):
        await client.complete(request())
    assert len(fake.calls) == 2  # le 3e essai n'est jamais parti
    with pytest.raises(CircuitOpenError):
        await client.complete(request())
    assert len(fake.calls) == 2
    assert client.breaker_for("anthropic").snapshot()["state"] == "open"


async def test_timeout_is_a_provider_error(make_client: ClientFactory) -> None:
    client, _ = make_client(
        FakeProvider(delay_s=0.05),
        default_timeout_s=0.01,
        retry_policy=RetryPolicy(max_attempts=1),
    )
    with pytest.raises(ProviderTimeoutError, match="anthropic"):
        await client.complete(request())


# ------------------------------------------------------------------ caches


async def test_exact_cache_hit_costs_nothing_and_skips_the_provider(
    make_client: ClientFactory, spans: InMemorySpanExporter
) -> None:
    client, fake = make_client(cache=InMemoryCache())
    first = await client.complete(request())
    second = await client.complete(request())
    assert len(fake.calls) == 1
    assert second.text == first.text
    assert second.cached
    assert second.cost_usd == 0.0
    attributes = dict(last_span(spans).attributes or {})
    assert attributes[Bench.CACHED] is True
    assert attributes[Bench.CACHE_KIND] == "exact"

    await client.complete(request(), use_cache=False)
    assert len(fake.calls) == 2


async def test_semantic_cache_serves_paraphrases_within_the_same_namespace(
    make_client: ClientFactory, spans: InMemorySpanExporter
) -> None:
    client, fake = make_client(
        cache=InMemoryCache(),
        semantic_cache=SemanticCacheConfig(embedding_model=EMBED, min_similarity=0.9),
    )
    embedder = FakeEmbedder()
    client.register_embedder("openai", embedder)

    await client.complete(request("Quelle est la capitale de la France ?"))
    hit = await client.complete(request("Capitale de la France ?"))
    assert len(fake.calls) == 1
    assert hit.cached
    attributes = dict(last_span(spans).attributes or {})
    assert attributes[Bench.CACHE_KIND] == "semantic"
    assert attributes[Bench.CACHE_SIMILARITY] == pytest.approx(1.0)

    await client.complete(request("Capitale de la France ?", system="Réponds en latin."))
    assert len(fake.calls) == 2  # autre system prompt = autre espace de noms

    assert all(call.data_class is DataClass.PUBLIC for call in embedder.calls)
    assert len(embedder.calls) == 3


# ------------------------------------------------------------------ flux et embeddings


async def test_stream_passes_chunks_and_prices_usage(
    make_client: ClientFactory, spans: InMemorySpanExporter
) -> None:
    budget = TokenBudget()
    client, _ = make_client(budget=budget)
    chunks = await drain(client.stream(request()))
    assert "".join(c.text for c in chunks) == "Bonjour"
    usage_chunk = next(c for c in chunks if c.kind == "usage")
    assert usage_chunk.cost_usd == pytest.approx(10 * 2e-6 + 5 * 10e-6)
    assert chunks[-1].finish_reason is FinishReason.STOP
    assert budget.spent_in_window() == 15
    attributes = dict(last_span(spans).attributes or {})
    assert attributes[GenAI.RESPONSE_MODEL] == "claude-sonnet-5"
    assert attributes[GenAI.USAGE_OUTPUT_TOKENS] == 5


async def test_stream_is_governed_and_feeds_the_breaker(make_client: ClientFactory) -> None:
    client, fake = make_client()
    with pytest.raises(GovernanceViolation):
        await drain(client.stream(request(data_class=DataClass.PERSONAL)))
    assert fake.calls == []

    failing = FakeProvider(script=[ProviderUnavailableError("503", backend="anthropic")])
    client, _ = make_client(
        failing,
        breaker_factory=lambda b: CircuitBreaker(backend=b, failure_threshold=1),
    )
    with pytest.raises(ProviderUnavailableError):
        await drain(client.stream(request()))
    with pytest.raises(CircuitOpenError):
        await drain(client.stream(request()))


async def test_embed_applies_governance_and_prices_input_tokens(
    make_client: ClientFactory, spans: InMemorySpanExporter
) -> None:
    client, _ = make_client()
    embedder = FakeEmbedder()
    client.register_embedder("openai", embedder)

    result = await client.embed(
        EmbeddingRequest(model=EMBED, texts=("abcd", "ef"), data_class=DataClass.PUBLIC)
    )
    assert result.dimensions == 2
    assert result.cost_usd == pytest.approx(6 * 0.02 / 1e6)
    attributes = dict(last_span(spans).attributes or {})
    assert attributes[GenAI.OPERATION_NAME] == "embeddings"
    assert attributes[GenAI.USAGE_INPUT_TOKENS] == 6

    with pytest.raises(GovernanceViolation, match="openai"):
        await client.embed(
            EmbeddingRequest(model=EMBED, texts=("x",), data_class=DataClass.CONFIDENTIAL)
        )
    assert len(embedder.calls) == 1
