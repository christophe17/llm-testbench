"""Parsing : du document brut à un document en sections.

Phase 1, volontairement minimal : texte brut, markdown (sections par titres), et
documents déjà sectionnés (texte intégral QASPER, titre + résumé BEIR). Le PDF et ses
pièges (colonnes, tableaux, notes de bas de page) arrivent en phase 3, où ils seront
**mesurés** — le parsing fait la moitié de la qualité d'un RAG, il mérite un chiffre.
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
        """Le texte complet, sections séparées par une ligne vide (pour affichage et
        empreinte ; le chunking travaille section par section)."""
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
    """Document déjà structuré : une suite de (titre de section, texte). Les sections
    vides sont écartées, l'ordre est conservé."""
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
    """Texte brut : une seule section, sans titre."""
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
    """Markdown : une section par titre ATX (``#`` à ``######``), le préambule avant le
    premier titre forme une section sans titre. Le titre du document est le premier
    ``#`` de niveau 1 si aucun n'est fourni. Les blocs de code ne sont pas traités
    spécialement : c'est un parseur de phase 1, pas un parseur de documentation."""
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
