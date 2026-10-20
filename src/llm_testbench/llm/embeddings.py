"""Embeddings contract: same logic as completions, same governance rules.

An embedding sends the text out exactly like a completion: the data class
is required and the policy applies. This is the point most often forgotten
when "securing" a RAG by looking only at the generator.
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.types import ModelRef, Usage

Vector = tuple[float, ...]


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: ModelRef
    texts: tuple[str, ...] = Field(min_length=1)
    data_class: DataClass
    dimensions: int | None = Field(default=None, ge=1)
    """Truncation requested from the provider when it supports it (OpenAI v3); ignored otherwise."""


class EmbeddingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    vectors: tuple[Vector, ...]
    model: str
    backend: str
    usage: Usage
    latency_ms: float = 0.0
    cost_usd: float | None = None
    usage_reported: bool = True

    @property
    def dimensions(self) -> int:
        return len(self.vectors[0]) if self.vectors else 0


@runtime_checkable
class EmbeddingProvider(Protocol):
    backend: str

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult: ...
