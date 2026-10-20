"""Sources the system can query (ADR 007): one interface, several origins.

Phase 1: documents (pgvector). Phase 4: SQL, API, structured data, images — same
provenance and citation types, same declared capabilities.
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
