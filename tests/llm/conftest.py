from collections.abc import Callable
from typing import Any

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.resilience import RetryPolicy
from llm_testbench.obs.tracing import configure_tracing, get_tracer
from tests.llm.fakes import FakeProvider


class FakeSleep:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


@pytest.fixture
def spans() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def fake_sleep() -> FakeSleep:
    return FakeSleep()


ClientFactory = Callable[..., tuple[LLMClient, FakeProvider]]


@pytest.fixture
def make_client(spans: InMemorySpanExporter, fake_sleep: FakeSleep) -> ClientFactory:
    """Fabrique un client sur la vraie configuration, avec un provider simulé injecté
    pour le backend ``anthropic`` et un exporteur de traces en mémoire."""

    def factory(
        provider: FakeProvider | None = None, **overrides: Any
    ) -> tuple[LLMClient, FakeProvider]:
        tracer_provider = configure_tracing(exporter=spans, set_global=False)
        options: dict[str, Any] = {
            "tracer": get_tracer(tracer_provider),
            "retry_policy": RetryPolicy(max_attempts=3, base_delay_s=0.0, jitter=0.0),
            "sleep": fake_sleep,
        }
        options.update(overrides)
        client = LLMClient.from_settings(**options)
        fake = provider if provider is not None else FakeProvider()
        client.register_provider("anthropic", fake)
        return client, fake

    return factory


def last_span(spans: InMemorySpanExporter) -> ReadableSpan:
    exported = spans.get_finished_spans()
    assert exported, "aucun span exporté"
    return exported[-1]
