"""API input/output schemas. Separate from the domain: what the client sees can evolve
without touching the internal types."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.types import Usage
from llm_testbench.sources.types import Citation, Evidence, Provenance


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4_000)
    k: int = Field(default=5, ge=1, le=20)
    data_class: DataClass = DataClass.PUBLIC
    """The testbench handles only public data; the field exists so that the governance
    policy is exercised end to end."""
    model: str | None = Field(default=None, description="backend/model, otherwise the default")


class EvidenceOut(BaseModel):
    rank: int
    score: float
    text: str
    provenance: Provenance
    metadata: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_evidence(cls, evidence: Evidence) -> "EvidenceOut":
        return cls(
            rank=evidence.rank,
            score=evidence.score,
            text=evidence.text,
            provenance=evidence.provenance,
            metadata=evidence.metadata,
        )


class CitationOut(BaseModel):
    index: int
    label: str
    provenance: Provenance

    @classmethod
    def from_citation(cls, citation: Citation) -> "CitationOut":
        return cls(index=citation.index, label=citation.label, provenance=citation.provenance)


class ChatResponse(BaseModel):
    answer: str
    refused: bool
    citations: list[CitationOut]
    unknown_citations: list[int]
    """Cited numbers without matching evidence: the answer is suspect."""
    evidence: list[EvidenceOut]
    model: str
    backend: str
    usage: Usage
    cost_usd: float | None
    latency_ms: float
    cached: bool
    attempts: int
    trace_id: str | None = None


class ChatEvent(BaseModel):
    """An event of the SSE stream: the evidence first, then the tokens, then the summary."""

    kind: Literal["retrieval", "token", "done", "error"]
    evidence: list[EvidenceOut] | None = None
    text: str | None = None
    answer: ChatResponse | None = None
    message: str | None = None


class SourceOut(BaseModel):
    key: str
    kind: str
    capabilities: list[str]
    description: str
    document_count: int | None


class ErrorOut(BaseModel):
    error: str
    detail: str
    reasons: list[str] = Field(default_factory=list)
