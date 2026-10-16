"""Contrat d'un provider LLM : ce que la façade attend, ce que chaque SDK traduit."""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from llm_testbench.llm.types import Completion, CompletionRequest, StreamChunk


@runtime_checkable
class LLMProvider(Protocol):
    backend: str
    native_json_schema: bool
    """True si le provider peut imposer un schéma JSON lui-même."""

    async def complete(self, request: CompletionRequest) -> Completion: ...

    def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]: ...
