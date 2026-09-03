"""Les deux providers, testés à travers les vrais SDK sur un transport HTTP simulé.

On ne mocke pas nos classes : on rejoue des réponses HTTP réalistes (JSON et flux SSE) et
on vérifie ce que le SDK envoie et ce que nous en faisons. Aucun test ne touche le réseau.
"""

import json
from collections.abc import Callable
from typing import Any

import anthropic
import httpx2
import openai
import pytest

from llm_testbench.llm.embeddings import EmbeddingRequest
from llm_testbench.llm.errors import (
    InvalidRequestError,
    LLMError,
    MissingCredentialsError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)
from llm_testbench.llm.providers import (
    AnthropicProvider,
    OpenAICompatibleProvider,
    OpenAIEmbeddingProvider,
    build_embedding_provider,
    build_provider,
)
from llm_testbench.llm.registry import Registry
from llm_testbench.llm.types import (
    CompletionRequest,
    DataClass,
    FinishReason,
    Message,
    ModelRef,
    Role,
)

Responder = Callable[[dict[str, Any]], httpx2.Response]


class Recorder:
    """Transport simulé : enregistre chaque corps de requête et répond selon ``responder``."""

    def __init__(self, responder: Responder) -> None:
        self.bodies: list[dict[str, Any]] = []
        self.headers: list[httpx2.Headers] = []
        self._responder = responder

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content or b"{}")
        self.bodies.append(body)
        self.headers.append(request.headers)
        return self._responder(body)

    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self)


def anthropic_provider(recorder: Recorder, **kwargs: Any) -> AnthropicProvider:
    client = anthropic.AsyncAnthropic(
        api_key="test",
        max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(transport=recorder.transport()),
    )
    return AnthropicProvider(backend="anthropic", client=client, **kwargs)


def openai_provider(
    recorder: Recorder,
    *,
    base_url: str = "https://api.openai.com/v1",
    **kwargs: Any,
) -> OpenAICompatibleProvider:
    client = openai.AsyncOpenAI(
        api_key="test",
        base_url=base_url,
        max_retries=0,
        http_client=openai.DefaultAsyncHttpxClient(transport=recorder.transport()),
    )
    kwargs.setdefault("native_json_schema", True)
    return OpenAICompatibleProvider(backend="openai", client=client, **kwargs)


def make_request(**overrides: Any) -> CompletionRequest:
    fields: dict[str, Any] = {
        "model": ModelRef.parse("anthropic/claude-sonnet-5"),
        "messages": (
            Message(role=Role.SYSTEM, content="Réponds en un mot."),
            Message(role=Role.USER, content="Bonjour ?"),
        ),
        "data_class": DataClass.PUBLIC,
        "max_output_tokens": 64,
        "temperature": 0.0,
    }
    fields.update(overrides)
    return CompletionRequest(**fields)


SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}

# ------------------------------------------------------------------ corps de réponse

ANTHROPIC_MESSAGE = {
    "id": "msg_01",
    "type": "message",
    "role": "assistant",
    "model": "claude-sonnet-5-served",
    "content": [{"type": "text", "text": "Bonjour"}],
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_read_input_tokens": 7,
        "cache_creation_input_tokens": 3,
    },
}


def anthropic_sse(text_parts: list[str], stop_reason: str = "end_turn") -> str:
    events: list[dict[str, Any]] = [
        {
            "type": "message_start",
            "message": {**ANTHROPIC_MESSAGE, "content": [], "stop_reason": None},
        },
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        *[
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": t}}
            for t in text_parts
        ],
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": 5},
        },
        {"type": "message_stop"},
    ]
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)


def openai_completion(
    *,
    content: str | None = "Bonjour",
    refusal: str | None = None,
    usage: dict[str, Any] | None = None,
    finish_reason: str = "stop",
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if refusal is not None:
        message["refusal"] = refusal
    body: dict[str, Any] = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": "gpt-served",
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
    }
    if usage is not None:
        body["usage"] = usage
    return body


def openai_sse(text_parts: list[str]) -> str:
    base = {"id": "chatcmpl-1", "object": "chat.completion.chunk", "created": 1, "model": "gpt-s"}
    chunks: list[dict[str, Any]] = [
        {**base, "choices": [{"index": 0, "delta": {"content": t}, "finish_reason": None}]}
        for t in text_parts
    ]
    chunks.append({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "length"}]})
    chunks.append(
        {
            **base,
            "choices": [],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
    )
    return "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"


def sse_response(payload: str) -> httpx2.Response:
    return httpx2.Response(
        200, content=payload.encode(), headers={"content-type": "text/event-stream"}
    )


# ================================================================== Anthropic


async def test_anthropic_translates_request_and_response() -> None:
    recorder = Recorder(lambda body: httpx2.Response(200, json=ANTHROPIC_MESSAGE))
    provider = anthropic_provider(recorder)

    completion = await provider.complete(make_request(seed=42, stop=("FIN",), timeout_s=5.0))

    body = recorder.bodies[0]
    assert body["model"] == "claude-sonnet-5"
    assert body["max_tokens"] == 64
    assert body["system"] == [
        {"type": "text", "text": "Réponds en un mot.", "cache_control": {"type": "ephemeral"}}
    ]
    assert body["messages"] == [{"role": "user", "content": "Bonjour ?"}]
    assert body["stop_sequences"] == ["FIN"]
    assert "temperature" not in body
    assert "seed" not in body
    assert recorder.headers[0]["x-api-key"] == "test"

    assert completion.text == "Bonjour"
    assert completion.model == "claude-sonnet-5-served"  # celui servi, pas celui demandé
    assert completion.backend == "anthropic"
    assert completion.usage.model_dump() == {
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_read_tokens": 7,
        "cache_write_tokens": 3,
    }
    assert completion.finish_reason is FinishReason.STOP
    assert completion.provider_message_id == "msg_01"
    assert completion.latency_ms > 0
    assert completion.usage_reported


async def test_anthropic_schema_and_effort_go_to_output_config() -> None:
    recorder = Recorder(lambda body: httpx2.Response(200, json=ANTHROPIC_MESSAGE))
    provider = anthropic_provider(recorder)
    await provider.complete(make_request(json_schema=SCHEMA, reasoning_effort="low"))
    assert recorder.bodies[0]["output_config"] == {
        "effort": "low",
        "format": {"type": "json_schema", "schema": SCHEMA},
    }

    prompt_mode = anthropic_provider(recorder, native_json_schema=False, cache_system_prompt=False)
    await prompt_mode.complete(make_request(json_schema=SCHEMA))
    assert "output_config" not in recorder.bodies[1]
    assert recorder.bodies[1]["system"] == [{"type": "text", "text": "Réponds en un mot."}]


async def test_anthropic_stream_yields_text_then_usage_then_end() -> None:
    recorder = Recorder(lambda body: sse_response(anthropic_sse(["Bon", "jour"], "max_tokens")))
    provider = anthropic_provider(recorder)

    chunks = [chunk async for chunk in provider.stream(make_request())]

    assert recorder.bodies[0]["stream"] is True
    assert [c.kind for c in chunks] == ["text", "text", "usage", "end"]
    assert "".join(c.text for c in chunks) == "Bonjour"
    assert chunks[2].usage is not None
    assert chunks[2].usage.output_tokens == 5
    assert chunks[2].usage.cache_read_tokens == 7
    assert chunks[3].finish_reason is FinishReason.LENGTH
    assert chunks[3].model == "claude-sonnet-5-served"


@pytest.mark.parametrize(
    ("status", "headers", "expected", "retryable", "retry_after"),
    [
        (429, {"retry-after": "7"}, RateLimitedError, True, 7.0),
        (429, {}, RateLimitedError, True, None),
        (529, {}, ProviderUnavailableError, True, None),
        (500, {}, ProviderUnavailableError, True, None),
        (400, {}, InvalidRequestError, False, None),
        (401, {}, InvalidRequestError, False, None),
    ],
)
async def test_anthropic_http_errors_become_typed_errors(
    status: int,
    headers: dict[str, str],
    expected: type[LLMError],
    retryable: bool,
    retry_after: float | None,
) -> None:
    error_body = {"type": "error", "error": {"type": "some_error", "message": "nope"}}
    recorder = Recorder(lambda body: httpx2.Response(status, json=error_body, headers=headers))
    provider = anthropic_provider(recorder)
    with pytest.raises(expected) as info:
        await provider.complete(make_request())
    assert info.value.retryable is retryable
    assert getattr(info.value, "status_code", status) == status
    assert getattr(info.value, "retry_after_s", None) == retry_after
    assert isinstance(info.value.__cause__, anthropic.APIStatusError)


async def test_anthropic_network_failures_become_retryable_errors() -> None:
    def broken(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused", request=request)

    def slow(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("read timed out", request=request)

    for handler, expected in ((broken, ProviderUnavailableError), (slow, ProviderTimeoutError)):
        client = anthropic.AsyncAnthropic(
            api_key="test",
            max_retries=0,
            http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)),
        )
        provider = AnthropicProvider(backend="anthropic", client=client)
        with pytest.raises(expected) as info:
            await provider.complete(make_request())
        assert info.value.retryable


# ================================================================== OpenAI-compatible


async def test_openai_normalizes_cached_tokens_and_uses_max_completion_tokens() -> None:
    usage = {
        "prompt_tokens": 100,
        "completion_tokens": 5,
        "total_tokens": 105,
        "prompt_tokens_details": {"cached_tokens": 40},
    }
    recorder = Recorder(lambda body: httpx2.Response(200, json=openai_completion(usage=usage)))
    provider = openai_provider(recorder, max_tokens_param="max_completion_tokens")

    completion = await provider.complete(
        make_request(model=ModelRef.parse("openai/gpt-5.6-luna"), seed=1, stop=("FIN",))
    )

    body = recorder.bodies[0]
    assert body["model"] == "gpt-5.6-luna"
    assert body["max_completion_tokens"] == 64
    assert "max_tokens" not in body
    assert body["temperature"] == 0.0
    assert body["seed"] == 1
    assert body["stop"] == ["FIN"]
    assert body["messages"][0] == {"role": "system", "content": "Réponds en un mot."}
    assert recorder.headers[0]["authorization"] == "Bearer test"

    assert completion.text == "Bonjour"
    assert completion.model == "gpt-served"
    assert completion.usage.input_tokens == 60
    assert completion.usage.cache_read_tokens == 40
    assert completion.usage.output_tokens == 5
    assert completion.finish_reason is FinishReason.STOP
    assert completion.usage_reported


async def test_openai_compatible_backend_uses_max_tokens_and_prompt_mode_schema() -> None:
    recorder = Recorder(lambda body: httpx2.Response(200, json=openai_completion()))
    provider = openai_provider(
        recorder, base_url="https://openrouter.ai/api/v1", native_json_schema=False
    )
    await provider.complete(make_request(json_schema=SCHEMA))
    body = recorder.bodies[0]
    assert body["max_tokens"] == 64
    assert "max_completion_tokens" not in body
    assert "response_format" not in body


async def test_openai_native_schema_uses_strict_response_format() -> None:
    recorder = Recorder(lambda body: httpx2.Response(200, json=openai_completion()))
    provider = openai_provider(recorder)
    await provider.complete(make_request(json_schema=SCHEMA, reasoning_effort="low"))
    body = recorder.bodies[0]
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "response", "schema": SCHEMA, "strict": True},
    }
    assert body["reasoning_effort"] == "low"


async def test_openai_refusal_and_missing_usage_are_visible() -> None:
    recorder = Recorder(
        lambda body: httpx2.Response(200, json=openai_completion(content=None, refusal="non"))
    )
    completion = await openai_provider(recorder).complete(make_request())
    assert completion.finish_reason is FinishReason.REFUSAL
    assert completion.text == ""
    assert completion.usage_reported is False
    assert completion.usage.total_tokens == 0


async def test_openai_stream_requests_usage_and_yields_chunks() -> None:
    recorder = Recorder(lambda body: sse_response(openai_sse(["Bon", "jour"])))
    provider = openai_provider(recorder)

    chunks = [chunk async for chunk in provider.stream(make_request())]

    body = recorder.bodies[0]
    assert body["stream"] is True
    assert body["stream_options"] == {"include_usage": True}
    assert [c.kind for c in chunks] == ["text", "text", "usage", "end"]
    assert "".join(c.text for c in chunks) == "Bonjour"
    assert chunks[2].usage is not None
    assert chunks[2].usage.output_tokens == 5
    assert chunks[3].finish_reason is FinishReason.LENGTH
    assert chunks[3].model == "gpt-s"


@pytest.mark.parametrize(
    ("status", "headers", "expected", "retryable", "retry_after"),
    [
        (429, {"retry-after": "2.5"}, RateLimitedError, True, 2.5),
        (503, {}, ProviderUnavailableError, True, None),
        (401, {}, InvalidRequestError, False, None),
        (404, {}, InvalidRequestError, False, None),
    ],
)
async def test_openai_http_errors_become_typed_errors(
    status: int,
    headers: dict[str, str],
    expected: type[LLMError],
    retryable: bool,
    retry_after: float | None,
) -> None:
    error_body = {"error": {"message": "nope", "type": "x", "code": None}}
    recorder = Recorder(lambda body: httpx2.Response(status, json=error_body, headers=headers))
    with pytest.raises(expected) as info:
        await openai_provider(recorder).complete(make_request())
    assert info.value.retryable is retryable
    assert getattr(info.value, "retry_after_s", None) == retry_after
    assert isinstance(info.value.__cause__, openai.APIStatusError)


# ================================================================== fabrique


def test_build_provider_reads_credentials_at_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = Registry.from_settings()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(MissingCredentialsError, match="ANTHROPIC_API_KEY"):
        build_provider("anthropic", registry.get("anthropic"))

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-a")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-o")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-r")
    claude = build_provider("anthropic", registry.get("anthropic"))
    assert isinstance(claude, AnthropicProvider)
    assert claude.native_json_schema

    direct = build_provider("openai", registry.get("openai"))
    assert isinstance(direct, OpenAICompatibleProvider)
    assert direct.max_tokens_param == "max_completion_tokens"
    assert direct.native_json_schema

    broker = build_provider("openrouter", registry.get("openrouter"))
    assert isinstance(broker, OpenAICompatibleProvider)
    assert broker.max_tokens_param == "max_tokens"
    assert not broker.native_json_schema

    local = build_provider("local", registry.get("local"))  # pas de clé requise
    assert isinstance(local, OpenAICompatibleProvider)
    assert local.backend == "local"


# ================================================================== embeddings


async def test_openai_embeddings_keep_input_order_and_report_usage() -> None:
    payload = {
        "object": "list",
        "model": "text-embedding-3-small",
        "data": [
            {"object": "embedding", "index": 1, "embedding": [0.0, 1.0]},
            {"object": "embedding", "index": 0, "embedding": [1.0, 0.0]},
        ],
        "usage": {"prompt_tokens": 6, "total_tokens": 6},
    }
    recorder = Recorder(lambda body: httpx2.Response(200, json=payload))
    client = openai.AsyncOpenAI(
        api_key="test",
        max_retries=0,
        http_client=openai.DefaultAsyncHttpxClient(transport=recorder.transport()),
    )
    provider = OpenAIEmbeddingProvider(backend="openai", client=client)

    result = await provider.embed(
        EmbeddingRequest(
            model=ModelRef.parse("openai/text-embedding-3-small"),
            texts=("premier", "second"),
            data_class=DataClass.PUBLIC,
            dimensions=2,
        )
    )

    assert recorder.bodies[0]["input"] == ["premier", "second"]
    assert recorder.bodies[0]["dimensions"] == 2
    assert result.vectors == ((1.0, 0.0), (0.0, 1.0))  # remis dans l'ordre d'entrée
    assert result.dimensions == 2
    assert result.usage.input_tokens == 6
    assert result.model == "text-embedding-3-small"


def test_embedding_factory_refuses_backends_without_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = Registry.from_settings()
    with pytest.raises(InvalidRequestError, match="ne fournit pas d'embeddings"):
        build_embedding_provider("anthropic", registry.get("anthropic"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-o")
    assert build_embedding_provider("openai", registry.get("openai")).backend == "openai"
