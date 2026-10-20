"""Parsing: from the raw document to a document in sections.

Phase 1, deliberately minimal: plain text, markdown (sections by headings), and
already-sectioned documents (QASPER full text, BEIR title + abstract). PDF and its
pitfalls (columns, tables, footnotes) arrive in phase 3, where they will be
**measured** — parsing makes half the quality of a RAG, it deserves a number.
"""

import hashlib
import re
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Section(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    text: str
    order: int = Field(ge=0)


class ParsedDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc_id: str = Field(min_length=1)
    title: str = ""
    sections: tuple[Section, ...]
    source_uri: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def text(self) -> str:
        """The full text, sections separated by a blank line (for display and
        fingerprint; chunking works section by section)."""
        return "\n\n".join(s.text for s in self.sections)

    @property
    def checksum(self) -> str:
        payload = "\x1f".join([self.title, *(f"{s.title}\x1e{s.text}" for s in self.sections)])
        return sha256_text(payload)

    @property
    def char_count(self) -> int:
        return sum(len(s.text) for s in self.sections)


def parse_sections(
    doc_id: str,
    sections: Iterable[tuple[str, str]],
    *,
    title: str = "",
    source_uri: str | None = None,
    metadata: dict[str, str] | None = None,
) -> ParsedDocument:
    """Already-structured document: a sequence of (section title, text). Empty
    sections are dropped, the order is kept."""
    kept = [
        Section(title=name.strip(), text=text.strip(), order=order)
        for order, (name, text) in enumerate(
            (name, text) for name, text in sections if text and text.strip()
        )
    ]
    return ParsedDocument(
        doc_id=doc_id,
        title=title.strip(),
        sections=tuple(kept),
        source_uri=source_uri,
        metadata=dict(metadata or {}),
    )


def parse_text(
    doc_id: str,
    text: str,
    *,
    title: str = "",
    source_uri: str | None = None,
    metadata: dict[str, str] | None = None,
) -> ParsedDocument:
    """Plain text: a single section, without a title."""
    return parse_sections(
        doc_id, [("", text)], title=title, source_uri=source_uri, metadata=metadata
    )


def parse_markdown(
    doc_id: str,
    text: str,
    *,
    title: str | None = None,
    source_uri: str | None = None,
    metadata: dict[str, str] | None = None,
) -> ParsedDocument:
    """Markdown: one section per ATX heading (``#`` to ``######``), the preamble before
    the first heading forms a section without a title. The document title is the first
    level-1 ``#`` if none is given. Code blocks are not handled specially: this is a
    phase 1 parser, not a documentation parser."""
    sections: list[tuple[str, str]] = []
    current_title = ""
    buffer: list[str] = []
    doc_title = title
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match is None:
            buffer.append(line)
            continue
        sections.append((current_title, "\n".join(buffer)))
        buffer = []
        current_title = match.group(2)
        if doc_title is None and len(match.group(1)) == 1:
            doc_title = current_title
    sections.append((current_title, "\n".join(buffer)))
    return parse_sections(
        doc_id, sections, title=doc_title or "", source_uri=source_uri, metadata=metadata
    )
