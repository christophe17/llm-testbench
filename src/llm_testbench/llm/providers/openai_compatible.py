"""Provider compatible OpenAI sur le SDK officiel — OpenAI, OpenRouter, Mistral, vLLM, Ollama.

Un seul code pour cinq backends, mais pas un seul comportement :

- **``max_tokens`` ou ``max_completion_tokens``** : OpenAI a déprécié le premier au profit
  du second ; les serveurs compatibles ne connaissent souvent que le premier. Le choix
  dépend de l'URL de base.
- **Usage en streaming** : il faut le demander (``stream_options.include_usage``), et il
  arrive dans un dernier morceau sans contenu. Certains serveurs compatibles ne le
  renvoient pas : l'usage est alors déclaré non rapporté, jamais nul.
- **Tokens cachés** : OpenAI les inclut dans ``prompt_tokens`` ; on les soustrait pour que
  ``input_tokens`` compte uniquement ce qui est facturé plein tarif.
- **Le SDK ne retente pas** (``max_retries=0``).
"""

from collections.abc import AsyncIterator
from typing import Any, Literal

import openai

from llm_testbench.llm.errors import (
    InvalidRequestError,
    LLMError,
    MissingCredentialsError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)
from llm_testbench.llm.providers._common import Stopwatch, retry_after_seconds
from llm_testbench.llm.registry import BackendConfig, StructuredOutputMode
from llm_testbench.llm.types import Completion, CompletionRequest, FinishReason, StreamChunk, Usage

_FINISH = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "content_filter": FinishReason.CONTENT_FILTER,
    "tool_calls": FinishReason.TOOL_USE,
    "function_call": FinishReason.TOOL_USE,
}

MaxTokensParam = Literal["max_tokens", "max_completion_tokens"]
_PLACEHOLDER_KEY = "not-needed"
"""Les serveurs locaux (Ollama, vLLM sans auth) exigent un en-tête, pas une vraie clé."""


def _finish(reason: str | None) -> FinishReason:
    return _FINISH.get(reason or "", FinishReason.OTHER)


def _usage(usage: openai.types.CompletionUsage | None) -> Usage | None:
    if usage is None:
        return None
    details = usage.prompt_tokens_details
    cached = (details.cached_tokens or 0) if details is not None else 0
    written = (details.cache_write_tokens or 0) if details is not None else 0
    return Usage(
        input_tokens=max(usage.prompt_tokens - cached - written, 0),
        output_tokens=usage.completion_tokens,
        cache_read_tokens=cached,
        cache_write_tokens=written,
    )


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        backend: str,
        client: openai.AsyncOpenAI,
        native_json_schema: bool,
        max_tokens_param: MaxTokensParam = "max_tokens",
    ) -> None:
        self.backend = backend
        self.native_json_schema = native_json_schema
        self.max_tokens_param: MaxTokensParam = max_tokens_param
        self._client = client

    @classmethod
    def from_config(cls, backend: str, config: BackendConfig) -> "OpenAICompatibleProvider":
        api_key = config.api_key()
        if api_key is None:
            if config.api_key_env is not None:
                raise MissingCredentialsError(
                    f"backend {backend!r} : variable d'environnement {config.api_key_env} absente"
                )
            api_key = _PLACEHOLDER_KEY
        client = openai.AsyncOpenAI(api_key=api_key, base_url=config.base_url, max_retries=0)
        is_openai = (config.base_url or "").startswith("https://api.openai.com")
        return cls(
            backend=backend,
            client=client,
            native_json_schema=config.structured_output is StructuredOutputMode.NATIVE,
            max_tokens_param="max_completion_tokens" if is_openai else "max_tokens",
        )

    # ------------------------------------------------------------------ traduction

    def build_params(self, request: CompletionRequest, *, stream: bool = False) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": request.model.model,
            "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
            self.max_tokens_param: request.max_output_tokens,
        }
        if request.temperature is not None:
            params["temperature"] = request.temperature
        if request.seed is not None:
            params["seed"] = request.seed
        if request.stop:
            params["stop"] = list(request.stop)
        if request.reasoning_effort is not None:
            params["reasoning_effort"] = request.reasoning_effort
        if request.json_schema is not None and self.native_json_schema:
            params["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": request.json_schema, "strict": True},
            }
        if request.timeout_s is not None:
            params["timeout"] = request.timeout_s
        if stream:
            params["stream"] = True
            params["stream_options"] = {"include_usage": True}
        return params

    def translate_error(self, error: Exception) -> LLMError:
        backend = self.backend
        if isinstance(error, openai.RateLimitError):
            return RateLimitedError(
                str(error),
                backend=backend,
                retry_after_s=retry_after_seconds(error.response.headers),
            )
        if isinstance(error, openai.APITimeoutError):
            return ProviderTimeoutError(str(error), backend=backend)
        if isinstance(error, openai.APIConnectionError):
            return ProviderUnavailableError(str(error), backend=backend)
        if isinstance(error, openai.APIStatusError):
            if error.status_code >= 500:
                return ProviderUnavailableError(
                    str(error), backend=backend, status_code=error.status_code
                )
            return InvalidRequestError(str(error), backend=backend, status_code=error.status_code)
        return ProviderUnavailableError(f"erreur inattendue : {error!r}", backend=backend)

    # ------------------------------------------------------------------ appels

    async def complete(self, request: CompletionRequest) -> Completion:
        params = self.build_params(request)
        watch = Stopwatch()
        try:
            response = await self._client.chat.completions.create(**params)
        except Exception as error:
            raise self.translate_error(error) from error
        choice = response.choices[0]
        usage = _usage(response.usage)
        refused = getattr(choice.message, "refusal", None)
        return Completion(
            text=choice.message.content or "",
            model=response.model,
            backend=self.backend,
            usage=usage if usage is not None else Usage(),
            usage_reported=usage is not None,
            finish_reason=FinishReason.REFUSAL if refused else _finish(choice.finish_reason),
            latency_ms=watch.elapsed_ms,
            provider_message_id=response.id,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        params = self.build_params(request, stream=True)
        usage: Usage | None = None
        finish: FinishReason = FinishReason.OTHER
        model: str | None = None
        try:
            response = await self._client.chat.completions.create(**params)
            async for chunk in response:
                model = chunk.model or model
                if chunk.choices:
                    choice = chunk.choices[0]
                    if choice.delta.content:
                        yield StreamChunk(kind="text", text=choice.delta.content)
                    if choice.finish_reason:
                        finish = _finish(choice.finish_reason)
                if chunk.usage is not None:
                    usage = _usage(chunk.usage)
        except Exception as error:
            raise self.translate_error(error) from error
        yield StreamChunk(kind="usage", usage=usage if usage is not None else Usage(), model=model)
        yield StreamChunk(kind="end", finish_reason=finish, model=model)
