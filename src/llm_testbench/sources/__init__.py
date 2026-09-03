"""Sources interrogeables par le système (ADR 007) : une interface, plusieurs origines.

Phase 1 : documents (pgvector). Phase 4 : SQL, API, données structurées, images — mêmes
types de provenance et de citation, mêmes capacités déclarées.
"""

from llm_testbench.sources.types import (
    Capability,
    Citation,
    Evidence,
    Provenance,
    SearchQuery,
    Source,
    SourceInfo,
    SourceKind,
)

__all__ = [
    "Capability",
    "Citation",
    "Evidence",
    "Provenance",
    "SearchQuery",
    "Source",
    "SourceInfo",
    "SourceKind",
]
