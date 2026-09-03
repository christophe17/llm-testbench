"""La façade ``LLMClient`` : l'ordre des maillons est le contrat (ADR 006).

Pour une complétion : **gouvernance** (refus avant tout appel) → **budget** (refus sur
estimation) → **cache** exact puis sémantique → **circuit breaker** → **retry** →
**provider** (avec délai) → **budget** (comptabilisation réelle) → **coût** → **trace**.
Chaque maillon est un objet injectable : le notebook 1 les fait tomber un par un.
"""

import asyncio
import random
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from opentelemetry import trace
from opentelemetry.trace import Span

from llm_testbench.config import Settings, get_settings
from llm_testbench.llm.budget import TokenBudget, estimate_tokens
from llm_testbench.llm.cache import CacheBackend, exact_key, semantic_namespace
from llm_testbench.llm.cost import PricingTable
from llm_testbench.llm.embeddings import EmbeddingProvider, EmbeddingRequest, EmbeddingResult
from llm_testbench.llm.governance import DataClass, GovernanceDecision, GovernancePolicy
from llm_testbench.llm.provider import LLMProvider
from llm_testbench.llm.providers import build_embedding_provider, build_provider
from llm_testbench.llm.registry import BackendConfig, Registry
from llm_testbench.llm.resilience import (
    CircuitBreaker,
    RetryPolicy,
    RetryReport,
    Sleeper,
    retry_call,
    with_timeout,
)
from llm_testbench.llm.types import (
    Completion,
    CompletionRequest,
    ModelRef,
    StreamChunk,
    Usage,
)
from llm_testbench.obs.tracing import Bench, GenAI, get_tracer

GOVERNANCE_FILENAME = "governance_policy.toml"

ProviderFactory = Callable[[str, BackendConfig], LLMProvider]
EmbeddingFactory = Callable[[str, BackendConfig], EmbeddingProvider]
BreakerFactory = Callable[[str], CircuitBreaker]


@dataclass(frozen=True)
class SemanticCacheConfig:
    embedding_model: ModelRef
    min_similarity: float = 0.95
    """Seuil élevé à dessein : un faux positif sert une réponse à une autre question."""


class LLMClient:
    def __init__(
        self,
        *,
        registry: Registry,
        policy: GovernancePolicy,
        pricing: PricingTable,
        provider_factory: ProviderFactory = build_provider,
        embedding_factory: EmbeddingFactory = build_embedding_provider,
        cache: CacheBackend | None = None,
        semantic_cache: SemanticCacheConfig | None = None,
        budget: TokenBudget | None = None,
        retry_policy: RetryPolicy | None = None,
        breaker_factory: BreakerFactory | None = None,
        default_timeout_s: float = 60.0,
        tracer: trace.Tracer | None = None,
        sleep: Sleeper = asyncio.sleep,
        rng: random.Random | None = None,
    ) -> None:
        self.registry = registry
        self.policy = policy
        self.pricing = pricing
        self.cache = cache
        self.semantic_cache = semantic_cache
        self.budget = budget
        self.retry_policy = retry_policy if retry_policy is not None else RetryPolicy()
        self.default_timeout_s = default_timeout_s
        self._provider_factory = provider_factory
        self._embedding_factory = embedding_factory
        self._breaker_factory = breaker_factory or (lambda backend: CircuitBreaker(backend=backend))
        self._tracer = tracer if tracer is not None else get_tracer()
        self._sleep = sleep
        self._rng = rng if rng is not None else random.Random()
        self._providers: dict[str, LLMProvider] = {}
        self._embedders: dict[str, EmbeddingProvider] = {}
        self._breakers: dict[str, CircuitBreaker] = {}

    @classmethod
    def from_settings(cls, settings: Settings | None = None, **overrides: object) -> "LLMClient":
        settings = settings if settings is not None else get_settings()
        config_dir = settings.resolved_config_dir()
        kwargs: dict[str, object] = {
            "registry": Registry.from_settings(settings),
            "policy": GovernancePolicy.load(config_dir / GOVERNANCE_FILENAME),
            "pricing": PricingTable.from_settings(settings),
        }
        kwargs.update(overrides)
        return cls(**kwargs)  # type: ignore[arg-type]

    # ------------------------------------------------------------------ composants

    def register_provider(self, backend: str, provider: LLMProvider) -> None:
        """Injecte un provider (tests, notebook : provider simulé qui tombe en panne)."""
        self._providers[backend] = provider

    def register_embedder(self, backend: str, provider: EmbeddingProvider) -> None:
        self._embedders[backend] = provider

    def provider_for(self, backend: str, config: BackendConfig) -> LLMProvider:
        if backend not in self._providers:
            self._providers[backend] = self._provider_factory(backend, config)
        return self._providers[backend]

    def embedder_for(self, backend: str, config: BackendConfig) -> EmbeddingProvider:
        if backend not in self._embedders:
            self._embedders[backend] = self._embedding_factory(backend, config)
        return self._embedders[backend]

    def breaker_for(self, backend: str) -> CircuitBreaker:
        if backend not in self._breakers:
            self._breakers[backend] = self._breaker_factory(backend)
        return self._breakers[backend]

    def native_json_schema(self, model: ModelRef) -> bool:
        ref, config = self.registry.resolve(model)
        return self.provider_for(ref.backend, config).native_json_schema

    # ------------------------------------------------------------------ maillons

    def _govern(
        self, span: Span, data_class: DataClass, backend: str, config: BackendConfig
    ) -> None:
        decision: GovernanceDecision = self.policy.evaluate(data_class, backend, config.governance)
        span.set_attribute(Bench.DATA_CLASS, data_class.value)
        span.set_attribute(Bench.INFERENCE_REGION, config.governance.inference_region.value)
        span.set_attribute(Bench.GOVERNANCE_ALLOWED, decision.allowed)
        if decision.reasons:
            span.set_attribute(Bench.GOVERNANCE_REASONS, list(decision.reasons))
        decision.enforce()

    async def _guarded[T](
        self, backend: str, timeout_s: float | None, call: Callable[[], Awaitable[T]]
    ) -> tuple[T, RetryReport]:
        """Breaker + retry + délai autour d'un appel provider."""
        report = RetryReport()
        timeout = timeout_s if timeout_s is not None else self.default_timeout_s

        async def attempt(_: int) -> T:
            return await with_timeout(call(), timeout, backend=backend)

        result = await retry_call(
            attempt,
            policy=self.retry_policy,
            breaker=self.breaker_for(backend),
            sleep=self._sleep,
            rng=self._rng,
            report=report,
        )
        return result, report

    def _cost(self, model: str, usage: Usage, reported: bool) -> float | None:
        return self.pricing.cost_usd(model, usage) if reported else None

    @staticmethod
    def _record_usage(span: Span, usage: Usage, cost: float | None) -> None:
        span.set_attribute(GenAI.USAGE_INPUT_TOKENS, usage.input_tokens)
        span.set_attribute(GenAI.USAGE_OUTPUT_TOKENS, usage.output_tokens)
        span.set_attribute(Bench.CACHE_READ_TOKENS, usage.cache_read_tokens)
        span.set_attribute(Bench.CACHE_WRITE_TOKENS, usage.cache_write_tokens)
        span.set_attribute(Bench.COST_KNOWN, cost is not None)
        if cost is not None:
            span.set_attribute(Bench.COST_USD, cost)

    @staticmethod
    def _request_attributes(span: Span, request: CompletionRequest, operation: str) -> None:
        span.set_attribute(GenAI.OPERATION_NAME, operation)
        span.set_attribute(GenAI.PROVIDER_NAME, request.model.backend)
        span.set_attribute(Bench.BACKEND, request.model.backend)
        span.set_attribute(GenAI.REQUEST_MODEL, request.model.model)
        span.set_attribute(GenAI.REQUEST_MAX_TOKENS, request.max_output_tokens)
        if request.temperature is not None:
            span.set_attribute(GenAI.REQUEST_TEMPERATURE, request.temperature)
        for key, attribute in (
            ("prompt.name", Bench.PROMPT_NAME),
            ("prompt.version", Bench.PROMPT_VERSION),
            ("prompt.sha256", Bench.PROMPT_SHA256),
        ):
            if key in request.metadata:
                span.set_attribute(attribute, request.metadata[key])

    async def _cache_lookup(
        self, span: Span, request: CompletionRequest, key: str, namespace: str | None
    ) -> tuple[Completion | None, tuple[float, ...] | None]:
        """Retourne (hit, vecteur du message utilisateur s'il a été calculé)."""
        assert self.cache is not None
        hit = await self.cache.get(key)
        if hit is not None:
            span.set_attribute(Bench.CACHE_KIND, "exact")
            return hit, None
        if namespace is None or self.semantic_cache is None:
            return None, None
        embedding = await self.embed(
            EmbeddingRequest(
                model=self.semantic_cache.embedding_model,
                texts=(request.turns[0].content,),
                data_class=request.data_class,
            )
        )
        vector = embedding.vectors[0]
        found = await self.cache.find_similar(namespace, vector, self.semantic_cache.min_similarity)
        if found is None:
            return None, vector
        span.set_attribute(Bench.CACHE_KIND, "semantic")
        span.set_attribute(Bench.CACHE_SIMILARITY, found[1])
        return found[0], vector

    # ------------------------------------------------------------------ API

    async def complete(self, request: CompletionRequest, *, use_cache: bool = True) -> Completion:
        with self._tracer.start_as_current_span(f"chat {request.model}") as span:
            self._request_attributes(span, request, "chat")
            ref, config = self.registry.resolve(request.model)
            backend = ref.backend
            self._govern(span, request.data_class, backend, config)

            estimated = sum(estimate_tokens(m.content) for m in request.messages)
            if self.budget is not None:
                self.budget.check(
                    estimated_input_tokens=estimated, max_output_tokens=request.max_output_tokens
                )

            key = exact_key(request)
            namespace = semantic_namespace(request)
            vector: tuple[float, ...] | None = None
            if self.cache is not None and use_cache:
                hit, vector = await self._cache_lookup(span, request, key, namespace)
                if hit is not None:
                    cached = hit.model_copy(
                        update={"cached": True, "cost_usd": 0.0, "latency_ms": 0.0}
                    )
                    span.set_attribute(Bench.CACHED, True)
                    self._record_usage(span, Usage(), 0.0)
                    return cached
            span.set_attribute(Bench.CACHED, False)

            provider = self.provider_for(backend, config)
            completion, report = await self._guarded(
                backend, request.timeout_s, lambda: provider.complete(request)
            )

            if self.budget is not None:
                self.budget.record(completion.usage)
            cost = self._cost(completion.model, completion.usage, completion.usage_reported)
            completion = completion.model_copy(update={"cost_usd": cost, "attempts": report.count})

            span.set_attribute(GenAI.RESPONSE_MODEL, completion.model)
            span.set_attribute(GenAI.RESPONSE_FINISH_REASONS, [completion.finish_reason.value])
            if completion.provider_message_id:
                span.set_attribute(GenAI.RESPONSE_ID, completion.provider_message_id)
            span.set_attribute(Bench.LATENCY_MS, completion.latency_ms)
            span.set_attribute(Bench.ATTEMPTS, report.count)
            self._record_usage(span, completion.usage, cost)

            if self.cache is not None and use_cache:
                await self.cache.put(key, completion)
                if namespace is not None and vector is not None:
                    await self.cache.put_vector(namespace, vector, key)
            return completion

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Flux sans cache et sans retry après le premier morceau : rejouer un flux entamé
        dupliquerait du texte déjà envoyé au client. Le breaker, lui, est consulté."""
        with self._tracer.start_as_current_span(f"chat {request.model}") as span:
            self._request_attributes(span, request, "chat")
            ref, config = self.registry.resolve(request.model)
            backend = ref.backend
            self._govern(span, request.data_class, backend, config)
            estimated = sum(estimate_tokens(m.content) for m in request.messages)
            if self.budget is not None:
                self.budget.check(
                    estimated_input_tokens=estimated, max_output_tokens=request.max_output_tokens
                )
            span.set_attribute(Bench.CACHED, False)
            breaker = self.breaker_for(backend)
            breaker.before_call()
            provider = self.provider_for(backend, config)
            try:
                async for chunk in provider.stream(request):
                    if chunk.kind == "usage" and chunk.usage is not None:
                        if self.budget is not None:
                            self.budget.record(chunk.usage)
                        cost = self._cost(chunk.model or request.model.model, chunk.usage, True)
                        self._record_usage(span, chunk.usage, cost)
                        chunk = chunk.model_copy(update={"cost_usd": cost})
                    elif chunk.kind == "end":
                        if chunk.model:
                            span.set_attribute(GenAI.RESPONSE_MODEL, chunk.model)
                        if chunk.finish_reason is not None:
                            span.set_attribute(
                                GenAI.RESPONSE_FINISH_REASONS, [chunk.finish_reason.value]
                            )
                    yield chunk
            except Exception as error:
                if CircuitBreaker.counts(error):
                    breaker.record_failure()
                raise
            breaker.record_success()

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        with self._tracer.start_as_current_span(f"embeddings {request.model}") as span:
            span.set_attribute(GenAI.OPERATION_NAME, "embeddings")
            span.set_attribute(GenAI.PROVIDER_NAME, request.model.backend)
            span.set_attribute(Bench.BACKEND, request.model.backend)
            span.set_attribute(GenAI.REQUEST_MODEL, request.model.model)
            ref, config = self.registry.resolve(request.model)
            backend = ref.backend
            self._govern(span, request.data_class, backend, config)
            embedder = self.embedder_for(backend, config)
            result, report = await self._guarded(backend, None, lambda: embedder.embed(request))
            if self.budget is not None:
                self.budget.record(result.usage)
            cost = self._cost(result.model, result.usage, result.usage_reported)
            span.set_attribute(GenAI.RESPONSE_MODEL, result.model)
            span.set_attribute(Bench.ATTEMPTS, report.count)
            span.set_attribute(Bench.LATENCY_MS, result.latency_ms)
            self._record_usage(span, result.usage, cost)
            return result.model_copy(update={"cost_usd": cost})
