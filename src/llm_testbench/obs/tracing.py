"""Traces OpenTelemetry (brief §4 : conventions sémantiques GenAI).

Deux familles d'attributs sur chaque span d'appel LLM :

- ``gen_ai.*`` : les noms standardisés par OpenTelemetry pour l'IA générative, pour que
  n'importe quel backend de traces (Langfuse, Grafana Tempo, Jaeger) sache les lire ;
- ``llm_testbench.*`` : ce que la convention ne couvre pas encore et que le banc mesure —
  coût, cache, tentatives, gouvernance, empreinte du prompt.

Configuration : ``configure_tracing`` installe un ``TracerProvider`` global avec, au choix,
un exporteur fourni (tests, notebook : mémoire ou console) ou un exporteur OTLP/HTTP vers
un endpoint (Langfuse en phase 1, collecteur OTel en phase 5). Sans configuration, les
spans sont des no-op : le code applicatif ne change pas.
"""

import base64
from collections.abc import Mapping
from typing import Final

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
)

TRACER_NAME: Final = "llm_testbench"


class GenAI:
    """Noms d'attributs, conventions sémantiques GenAI d'OpenTelemetry (version 1.3x)."""

    OPERATION_NAME: Final = "gen_ai.operation.name"
    PROVIDER_NAME: Final = "gen_ai.provider.name"
    REQUEST_MODEL: Final = "gen_ai.request.model"
    REQUEST_MAX_TOKENS: Final = "gen_ai.request.max_tokens"
    REQUEST_TEMPERATURE: Final = "gen_ai.request.temperature"
    RESPONSE_MODEL: Final = "gen_ai.response.model"
    RESPONSE_ID: Final = "gen_ai.response.id"
    RESPONSE_FINISH_REASONS: Final = "gen_ai.response.finish_reasons"
    USAGE_INPUT_TOKENS: Final = "gen_ai.usage.input_tokens"
    USAGE_OUTPUT_TOKENS: Final = "gen_ai.usage.output_tokens"


class Bench:
    """Attributs propres au banc d'essai."""

    BACKEND: Final = "llm_testbench.backend"
    LATENCY_MS: Final = "llm_testbench.latency_ms"
    COST_USD: Final = "llm_testbench.cost_usd"
    COST_KNOWN: Final = "llm_testbench.cost_known"
    CACHE_READ_TOKENS: Final = "llm_testbench.usage.cache_read_tokens"
    CACHE_WRITE_TOKENS: Final = "llm_testbench.usage.cache_write_tokens"
    CACHED: Final = "llm_testbench.cache.hit"
    CACHE_KIND: Final = "llm_testbench.cache.kind"
    CACHE_SIMILARITY: Final = "llm_testbench.cache.similarity"
    ATTEMPTS: Final = "llm_testbench.attempts"
    DATA_CLASS: Final = "llm_testbench.governance.data_class"
    GOVERNANCE_ALLOWED: Final = "llm_testbench.governance.allowed"
    GOVERNANCE_REASONS: Final = "llm_testbench.governance.reasons"
    INFERENCE_REGION: Final = "llm_testbench.governance.inference_region"
    PROMPT_NAME: Final = "llm_testbench.prompt.name"
    PROMPT_VERSION: Final = "llm_testbench.prompt.version"
    PROMPT_SHA256: Final = "llm_testbench.prompt.sha256"


def langfuse_otlp_headers(public_key: str, secret_key: str) -> dict[str, str]:
    """Langfuse authentifie l'OTLP par Basic auth ``clé publique:clé secrète``."""
    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def configure_tracing(
    *,
    service_name: str = "llm-testbench",
    exporter: SpanExporter | None = None,
    otlp_endpoint: str | None = None,
    otlp_headers: Mapping[str, str] | None = None,
    set_global: bool = True,
) -> TracerProvider:
    """Installe un fournisseur de traces.

    ``exporter`` fourni → traitement synchrone (tests, notebooks : chaque span est visible
    tout de suite). Sinon, ``otlp_endpoint`` → export OTLP/HTTP par lots. Ni l'un ni
    l'autre → fournisseur sans exporteur (les spans existent, personne ne les lit).
    """
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    elif otlp_endpoint is not None:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=otlp_endpoint, headers=dict(otlp_headers or {}))
            )
        )
    if set_global:
        trace.set_tracer_provider(provider)
    return provider


def get_tracer(provider: TracerProvider | None = None) -> trace.Tracer:
    if provider is not None:
        return provider.get_tracer(TRACER_NAME)
    return trace.get_tracer(TRACER_NAME)
