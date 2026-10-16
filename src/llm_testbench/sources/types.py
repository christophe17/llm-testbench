"""Types communs à toutes les sources (ADR 007).

Le point structurant : la **provenance** et la **citation** ont la même forme pour un
chunk de document, une ligne SQL (phase 4) ou une réponse d'API. Le générateur ne sait
pas d'où vient une preuve ; il la cite par son numéro, et c'est la provenance qui dit
au lecteur où aller vérifier.
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
    """Recherche par similarité ou par mots-clés : la capacité de base d'un RAG."""
    FETCH = "fetch"
    """Récupération d'un document entier par identifiant."""
    FILTER = "filter"
    """Filtrage par métadonnées lors de la recherche."""
    QUERY = "query"
    """Exécution d'une requête (SQL) — phase 4."""
    CALL = "call"
    """Appel d'une opération d'API — phase 4."""


class Provenance(BaseModel):
    """D'où vient une preuve, assez précisément pour qu'un humain aille vérifier."""

    model_config = ConfigDict(frozen=True)

    source_key: str
    document_id: str
    chunk_id: str | None = None
    locator: str
    """Localisation lisible dans le document : section et position, page, plage de lignes…"""
    title: str | None = None
    uri: str | None = None
    checksum: str | None = None
    """Empreinte du texte cité : la preuve qu'on cite ce qui a été indexé, pas autre chose."""
    ingested_at: dt.datetime | None = None
    extra: dict[str, str] = Field(default_factory=dict)

    def label(self) -> str:
        parts = [self.source_key, self.title or self.document_id]
        if self.locator:
            parts.append(self.locator)
        return " › ".join(parts)


class Evidence(BaseModel):
    """Un élément de contexte retourné par une source, avec son score et sa provenance."""

    model_config = ConfigDict(frozen=True)

    text: str
    score: float
    rank: int = Field(ge=1)
    provenance: Provenance
    metadata: dict[str, str] = Field(default_factory=dict)


class Citation(BaseModel):
    """Ce que le lecteur voit : ``[n]`` puis un libellé homogène quelle que soit la source."""

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
    """La question part dehors (embedding) : elle a une classe de données, comme tout."""


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
