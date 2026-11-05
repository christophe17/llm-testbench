"""Embeddings contract: same logic as completions, same governance rules.

An embedding sends the text out exactly like a completion: the data class
is required and the policy applies. This is the point most often forgotten
when "securing" a RAG by looking only at the generator.
"""

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.types import ModelRef, Usage

Vector = tuple[float, ...]

InputType = Literal["document", "query"]


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: ModelRef
    texts: tuple[str, ...] = Field(min_length=1)
    data_class: DataClass
    dimensions: int | None = Field(default=None, ge=1)
    """Truncation requested from the provider when it supports it (OpenAI v3); ignored otherwise."""
    input_type: InputType = "document"
    """Which side of a search the texts are on. Many retrieval models are asymmetric: the
    question gets an instruction the passages do not (bge: "Represent this sentence for
    searching relevant passages: "). A provider without that notion (OpenAI) ignores it;
    one with it applies it. Forgetting it costs a fraction of a point, silently."""


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
