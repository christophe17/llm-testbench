"""L'application FastAPI et son câblage.

``create_app`` accepte des composants injectés (client LLM, source) pour les tests et le
notebook ; en production, le cycle de vie ouvre le pool Postgres, vérifie le schéma,
retrouve l'index configuré dans le registre et construit la source documentaire. Si
l'index n'existe pas, l'API démarre mais ``/readyz`` répond 503 avec la raison : un pod
qui ne peut pas répondre ne doit pas recevoir de trafic, et doit dire pourquoi.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from opentelemetry import trace

from llm_testbench.app.chat import ChatService
from llm_testbench.app.schemas import ChatRequest, ChatResponse, ErrorOut, SourceOut
from llm_testbench.app.sse import SSE_HEADERS, until_disconnected
from llm_testbench.config import Settings, get_settings
from llm_testbench.generation.answer import AnswerBuilder
from llm_testbench.ingest.store import PgVectorStore
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.errors import (
    BackendDisabledError,
    BudgetExceededError,
    CircuitOpenError,
    GovernanceViolation,
    InvalidRequestError,
    LLMError,
    MissingCredentialsError,
    ProviderError,
    RateLimitedError,
    UnknownBackendError,
)
from llm_testbench.llm.prompts import PromptRegistry
from llm_testbench.llm.types import ModelRef
from llm_testbench.obs.tracing import configure_tracing, langfuse_otlp_headers
from llm_testbench.sources.documents import DocumentSource
from llm_testbench.sources.types import Source


def _error(status: int, error: str, detail: str, reasons: list[str] | None = None) -> JSONResponse:
    body = ErrorOut(error=error, detail=detail, reasons=reasons or [])
    return JSONResponse(status_code=status, content=body.model_dump())


def _map_llm_error(error: LLMError) -> JSONResponse:
    if isinstance(error, GovernanceViolation):
        return _error(403, "governance", str(error), list(error.reasons))
    if isinstance(error, BudgetExceededError):
        return _error(429, "budget", str(error))
    if isinstance(error, CircuitOpenError):
        response = _error(503, "circuit_open", str(error))
        response.headers["Retry-After"] = str(max(int(error.retry_in_s), 1))
        return response
    if isinstance(error, RateLimitedError):
        response = _error(429, "rate_limited", str(error))
        if error.retry_after_s is not None:
            response.headers["Retry-After"] = str(max(int(error.retry_after_s), 1))
        return response
    if isinstance(error, InvalidRequestError):
        return _error(502, "upstream_rejected", str(error))
    if isinstance(error, ProviderError):
        return _error(503, "upstream_unavailable", str(error))
    if isinstance(error, UnknownBackendError | BackendDisabledError):
        return _error(400, "unknown_backend", str(error))
    if isinstance(error, MissingCredentialsError):
        return _error(500, "missing_credentials", str(error))
    return _error(500, "llm_error", str(error))


def _configure_tracing_from(settings: Settings) -> None:
    if settings.otlp_endpoint is None:
        return
    headers = None
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        headers = langfuse_otlp_headers(settings.langfuse_public_key, settings.langfuse_secret_key)
    configure_tracing(
        service_name=settings.service_name,
        otlp_endpoint=settings.otlp_endpoint,
        otlp_headers=headers,
    )


def create_app(
    settings: Settings | None = None,
    *,
    llm_client: LLMClient | None = None,
    source: Source | None = None,
    tracer: trace.Tracer | None = None,
) -> FastAPI:
    settings = settings if settings is not None else get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        state: dict[str, Any] = {"ready": False, "reason": "démarrage", "store": None}
        app.state.bench = state
        _configure_tracing_from(settings)
        client = (
            llm_client
            if llm_client is not None
            else LLMClient.from_settings(settings, tracer=tracer)
        )
        default_model = (
            ModelRef.parse(settings.chat_model)
            if settings.chat_model
            else client.registry.defaults.generator
        )
        chosen_source = source
        if chosen_source is None:
            if settings.database_url is None:
                state["reason"] = "LLM_TESTBENCH_DATABASE_URL absent"
            else:
                store = PgVectorStore.from_url(settings.database_url)
                await store.open()
                state["store"] = store
                await store.ensure_schema()
                spec = await store.get_index(settings.index_key)
                if spec is None:
                    state["reason"] = (
                        f"index {settings.index_key!r} absent du registre : lancer l'ingestion"
                    )
                else:
                    chosen_source = DocumentSource(client=client, store=store, spec=spec)
        if chosen_source is not None:
            state["service"] = ChatService(
                client=client,
                source=chosen_source,
                builder=AnswerBuilder(PromptRegistry.from_settings(settings)),
                default_model=default_model,
            )
            state["source"] = chosen_source
            state["ready"], state["reason"] = True, "ok"
        try:
            yield
        finally:
            if state["store"] is not None:
                await state["store"].close()

    app = FastAPI(
        title="llm-testbench",
        version="0.1.0",
        summary="Banc d'essai LLM chiffré — API de démonstration (phase 1)",
        lifespan=lifespan,
    )

    @app.exception_handler(LLMError)
    async def _llm_error_handler(_: Request, error: LLMError) -> JSONResponse:
        return _map_llm_error(error)

    def _service(request: Request) -> ChatService:
        state = request.app.state.bench
        if not state["ready"]:
            raise ServiceUnavailable(state["reason"])
        service: ChatService = state["service"]
        return service

    @app.exception_handler(ServiceUnavailable)
    async def _unavailable_handler(_: Request, error: "ServiceUnavailable") -> JSONResponse:
        return _error(503, "not_ready", str(error))

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz(request: Request) -> Response:
        state = request.app.state.bench
        if state["ready"]:
            return JSONResponse({"status": "ready"})
        return _error(503, "not_ready", state["reason"])

    @app.get("/sources", response_model=list[SourceOut])
    async def sources(request: Request) -> list[SourceOut]:
        _service(request)  # 503 si l'API n'est pas prête
        source_obj: Source = request.app.state.bench["source"]
        info = await source_obj.describe()
        return [
            SourceOut(
                key=info.key,
                kind=info.kind.value,
                capabilities=sorted(c.value for c in info.capabilities),
                description=info.description,
                document_count=info.document_count,
            )
        ]

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: Request, body: ChatRequest) -> ChatResponse:
        return await _service(request).answer(body)

    @app.post("/chat/stream")
    async def chat_stream(request: Request, body: ChatRequest) -> StreamingResponse:
        service = _service(request)
        events = until_disconnected(
            service.stream(body),
            is_disconnected=request.is_disconnected,
            kind=lambda event: event.kind,
        )
        return StreamingResponse(events, media_type="text/event-stream", headers=SSE_HEADERS)

    return app


class ServiceUnavailable(RuntimeError):
    """L'API tourne mais ne peut pas répondre (base absente, index non construit)."""


app = create_app()
