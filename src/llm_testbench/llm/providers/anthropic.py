"""Provider Anthropic sur le SDK officiel — sert aussi Bedrock (même API Messages).

Traductions à connaître, parce qu'elles surprennent :

- **``temperature`` et ``seed`` sont ignorés.** Les modèles Claude actuels (Sonnet 5,
  Opus 5, Fable 5) refusent tout paramètre d'échantillonnage avec un 400. Le réflexe
  « température 0 pour le déterminisme » est un réflexe de 2024 ; la phase 5B mesurera
  le déterminisme réel sans lui.
- **Le system prompt est marqué cacheable.** Anthropic ne cache que ce qu'on lui demande
  de cacher (``cache_control``), et seulement au-delà d'une taille minimale par modèle :
  sur un prompt court, ``cache_read_tokens`` restera à zéro, c'est normal.
- **Le SDK ne retente pas** (``max_retries=0``) : la politique de retry est la nôtre.
"""

from collections.abc import AsyncIterator
from typing import Any

import anthropic

from llm_testbench.llm.errors import (
    InvalidRequestError,
    LLMError,
    MissingCredentialsError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)
from llm_testbench.llm.providers._common import Stopwatch, retry_after_seconds
from llm_testbench.llm.registry import BackendConfig, BackendKind, StructuredOutputMode
from llm_testbench.llm.types import Completion, CompletionRequest, FinishReason, StreamChunk, Usage

AnthropicClient = anthropic.AsyncAnthropic | anthropic.AsyncAnthropicBedrockMantle

_FINISH = {
    "end_turn": FinishReason.STOP,
    "stop_sequence": FinishReason.STOP,
    "max_tokens": FinishReason.LENGTH,
    "refusal": FinishReason.REFUSAL,
    "tool_use": FinishReason.TOOL_USE,
}


def _finish(stop_reason: str | None) -> FinishReason:
    return _FINISH.get(stop_reason or "", FinishReason.OTHER)


def _usage(usage: anthropic.types.Usage) -> Usage:
    return Usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_input_tokens or 0,
        cache_write_tokens=usage.cache_creation_input_tokens or 0,
    )


class AnthropicProvider:
    def __init__(
        self,
        *,
        backend: str,
        client: AnthropicClient,
        native_json_schema: bool = True,
        cache_system_prompt: bool = True,
    ) -> None:
        self.backend = backend
        self.native_json_schema = native_json_schema
        self.cache_system_prompt = cache_system_prompt
        self._client = client

    @classmethod
    def from_config(cls, backend: str, config: BackendConfig) -> "AnthropicProvider":
        client: AnthropicClient
        if config.kind is BackendKind.ANTHROPIC_BEDROCK:
            client = anthropic.AsyncAnthropicBedrockMantle(aws_region=config.region, max_retries=0)
        else:
            api_key = config.api_key()
            if api_key is None:
                raise MissingCredentialsError(
                    f"backend {backend!r} : variable d'environnement {config.api_key_env} absente"
                )
            client = anthropic.AsyncAnthropic(
                api_key=api_key, base_url=config.base_url, max_retries=0
            )
        return cls(
            backend=backend,
            client=client,
            native_json_schema=config.structured_output is StructuredOutputMode.NATIVE,
        )

    # ------------------------------------------------------------------ traduction

    def build_params(self, request: CompletionRequest) -> dict[str, Any]:
        """La requête neutre → les paramètres du SDK. Public : le notebook l'affiche."""
        params: dict[str, Any] = {
            "model": request.model.model,
            "max_tokens": request.max_output_tokens,
            "messages": [{"role": m.role.value, "content": m.content} for m in request.turns],
        }
        if request.system is not None:
            block: dict[str, Any] = {"type": "text", "text": request.system}
            if self.cache_system_prompt:
                block["cache_control"] = {"type": "ephemeral"}
            params["system"] = [block]
        if request.stop:
            params["stop_sequences"] = list(request.stop)
        output_config: dict[str, Any] = {}
        if request.reasoning_effort is not None:
            output_config["effort"] = request.reasoning_effort
        if request.json_schema is not None and self.native_json_schema:
            output_config["format"] = {"type": "json_schema", "schema": request.json_schema}
        if output_config:
            params["output_config"] = output_config
        if request.timeout_s is not None:
            params["timeout"] = request.timeout_s
        return params

    def translate_error(self, error: Exception) -> LLMError:
        backend = self.backend
        if isinstance(error, anthropic.RateLimitError):
            return RateLimitedError(
                str(error),
                backend=backend,
                retry_after_s=retry_after_seconds(error.response.headers),
            )
        if isinstance(error, anthropic.APITimeoutError):
            return ProviderTimeoutError(str(error), backend=backend)
        if isinstance(error, anthropic.APIConnectionError):
            return ProviderUnavailableError(str(error), backend=backend)
        if isinstance(error, anthropic.APIStatusError):
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
            message = await self._client.messages.create(**params)
        except Exception as error:
            raise self.translate_error(error) from error
        text = "".join(block.text for block in message.content if block.type == "text")
        return Completion(
            text=text,
            model=message.model,
            backend=self.backend,
            usage=_usage(message.usage),
            finish_reason=_finish(message.stop_reason),
            latency_ms=watch.elapsed_ms,
            provider_message_id=message.id,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        params = self.build_params(request)
        try:
            async with self._client.messages.stream(**params) as stream:
                async for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and event.delta.type == "text_delta"
                        and event.delta.text
                    ):
                        yield StreamChunk(kind="text", text=event.delta.text)
                final = await stream.get_final_message()
        except Exception as error:
            raise self.translate_error(error) from error
        yield StreamChunk(kind="usage", usage=_usage(final.usage), model=final.model)
        yield StreamChunk(kind="end", finish_reason=_finish(final.stop_reason), model=final.model)
