"""Contract of an LLM provider: what the facade expects, what each SDK translates."""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from llm_testbench.llm.types import Completion, CompletionRequest, StreamChunk


@runtime_checkable
class LLMProvider(Protocol):
    backend: str
    native_json_schema: bool
    """True if the provider can enforce a JSON schema itself."""

    async def complete(self, request: CompletionRequest) -> Completion: ...

    def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]: ...
