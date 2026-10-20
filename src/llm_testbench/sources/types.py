"""Types common to all sources (ADR 007).

The structuring point: **provenance** and **citation** have the same shape for a
document chunk, an SQL row (phase 4) or an API response. The generator does not know
where a piece of evidence comes from; it cites it by its number, and it is the
provenance that tells the reader where to go and check.
"""

import datetime as dt
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from llm_testbench.llm.governance import DataClass


class SourceKind(StrEnum):
    DOCUMENTS = "documents"
    SQL = "sql"
    API = "api"
    STRUCTURED = "structured"
    IMAGES = "images"


class Capability(StrEnum):
    SEARCH = "search"
    """Search by similarity or by keywords: the basic capability of a RAG."""
    FETCH = "fetch"
    """Retrieval of a whole document by identifier."""
    FILTER = "filter"
    """Filtering by metadata during the search."""
    QUERY = "query"
    """Execution of a query (SQL) — phase 4."""
    CALL = "call"
    """Call of an API operation — phase 4."""


class Provenance(BaseModel):
    """Where a piece of evidence comes from, precisely enough for a human to go and check."""

    model_config = ConfigDict(frozen=True)

    source_key: str
    document_id: str
    chunk_id: str | None = None
    locator: str
    """Readable location in the document: section and position, page, line range…"""
    title: str | None = None
    uri: str | None = None
    checksum: str | None = None
    """Fingerprint of the cited text: proof that we cite what was indexed, nothing else."""
    ingested_at: dt.datetime | None = None
    extra: dict[str, str] = Field(default_factory=dict)

    def label(self) -> str:
        parts = [self.source_key, self.title or self.document_id]
        if self.locator:
            parts.append(self.locator)
        return " › ".join(parts)


class Evidence(BaseModel):
    """A context item returned by a source, with its score and its provenance."""

    model_config = ConfigDict(frozen=True)

    text: str
    score: float
    rank: int = Field(ge=1)
    provenance: Provenance
    metadata: dict[str, str] = Field(default_factory=dict)


class Citation(BaseModel):
    """What the reader sees: ``[n]`` then a uniform label whatever the source."""

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=1)
    label: str
    provenance: Provenance

    @classmethod
    def from_evidence(cls, index: int, evidence: Evidence) -> "Citation":
        return cls(index=index, label=evidence.provenance.label(), provenance=evidence.provenance)

    def render(self) -> str:
        return f"[{self.index}] {self.label}"


class SearchQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=50)
    filters: dict[str, str] = Field(default_factory=dict)
    data_class: DataClass
    """The question goes outside (embedding): it has a data class, like everything."""


class SourceInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    kind: SourceKind
    capabilities: frozenset[Capability]
    description: str = ""
    document_count: int | None = None


@runtime_checkable
class Source(Protocol):
    key: str
    kind: SourceKind
    capabilities: frozenset[Capability]

    async def search(self, query: SearchQuery) -> list[Evidence]: ...

    async def fetch(self, document_id: str) -> Evidence | None: ...

    async def describe(self) -> SourceInfo: ...
