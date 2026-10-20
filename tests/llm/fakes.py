"""Simulated providers to test the facade without SDK or network."""

import asyncio
from collections.abc import AsyncIterator

from llm_testbench.llm.embeddings import EmbeddingRequest, EmbeddingResult
from llm_testbench.llm.types import (
    Completion,
    CompletionRequest,
    FinishReason,
    StreamChunk,
    Usage,
)


def make_completion(
    text: str = "answer",
    *,
    model: str = "claude-sonnet-5",
    input_tokens: int = 1_000,
    output_tokens: int = 500,
    backend: str = "anthropic",
) -> Completion:
    return Completion(
        text=text,
        model=model,
        backend=backend,
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
        finish_reason=FinishReason.STOP,
        latency_ms=12.0,
        provider_message_id="msg_fake",
    )


class FakeProvider:
    """Replays a scenario: each call consumes the next item (response or error)."""

    def __init__(
        self,
        backend: str = "anthropic",
        *,
        native_json_schema: bool = True,
        script: list[Completion | Exception] | None = None,
        delay_s: float = 0.0,
    ) -> None:
        self.backend = backend
        self.native_json_schema = native_json_schema
        self.delay_s = delay_s
        self.calls: list[CompletionRequest] = []
        self._script = list(script or [])

    async def complete(self, request: CompletionRequest) -> Completion:
        self.calls.append(request)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        item = self._script.pop(0) if self._script else make_completion()
        if isinstance(item, Exception):
            raise item
        return item

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        self.calls.append(request)
        if self._script and isinstance(self._script[0], Exception):
            raise self._script.pop(0)
        for part in ("Hel", "lo"):
            yield StreamChunk(kind="text", text=part)
        yield StreamChunk(
            kind="usage", usage=Usage(input_tokens=10, output_tokens=5), model="claude-sonnet-5"
        )
        yield StreamChunk(kind="end", finish_reason=FinishReason.STOP, model="claude-sonnet-5")


def toy_vector(text: str) -> tuple[float, ...]:
    """Only two "meanings": paraphrases of the same question share a vector."""
    return (1.0, 0.0) if "capital" in text.lower() else (0.0, 1.0)


class FakeEmbedder:
    def __init__(self, backend: str = "openai") -> None:
        self.backend = backend
        self.calls: list[EmbeddingRequest] = []

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        self.calls.append(request)
        return EmbeddingResult(
            vectors=tuple(toy_vector(t) for t in request.texts),
            model="text-embedding-3-small",
            backend=self.backend,
            usage=Usage(input_tokens=sum(len(t) for t in request.texts)),
            latency_ms=1.0,
        )
