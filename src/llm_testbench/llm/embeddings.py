"""Contrat des embeddings : même logique que les complétions, mêmes règles de gouvernance.

Un embedding envoie le texte dehors exactement comme une complétion : la classe de
données est obligatoire et la politique s'applique. C'est le point que l'on oublie le plus
souvent quand on « sécurise » un RAG en ne regardant que le générateur.
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
    """Troncature demandée au provider quand il la supporte (OpenAI v3) ; sinon ignorée."""


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
