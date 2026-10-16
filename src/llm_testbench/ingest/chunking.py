"""Chunking récursif par séparateurs — la baseline naïve que la phase 3 doit battre.

Principe : on essaie de couper sur le séparateur le plus « naturel » (paragraphe), et si
un morceau reste trop long, on descend d'un cran (ligne, phrase, mot, caractère). Les
morceaux sont ensuite regroupés jusqu'à ``chunk_size`` caractères, avec un
chevauchement ``chunk_overlap`` pour ne pas couper une idée en deux sans témoin.

Ce qui rend ce chunker naïf, et qu'on mesurera : il ignore la structure (un tableau, une
liste, une note), coupe les phrases longues au milieu, et ne sait rien du contenu. Il est
réécrit ici (plutôt qu'importé) pour tenir en une page lisible dans le notebook 2.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from llm_testbench.ingest.parsing import ParsedDocument, sha256_text
from llm_testbench.llm.budget import estimate_tokens

DEFAULT_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", ". ", " ", "")


class Chunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: str
    doc_id: str
    ordinal: int = Field(ge=0)
    text: str = Field(min_length=1)
    section_title: str = ""
    section_order: int = Field(ge=0)
    start_char: int = Field(ge=0)
    """Position dans le texte de la section (pas du document) : ``section.text[start:end]``."""
    end_char: int = Field(ge=0)
    checksum: str
    token_estimate: int = Field(ge=0)

    def locator(self) -> str:
        section = f"section « {self.section_title} »" if self.section_title else "texte"
        return f"{section}, caractères {self.start_char}–{self.end_char}"


def _split_keep(text: str, separator: str) -> list[str]:
    """Découpe en gardant le séparateur à la fin de chaque morceau : la concaténation
    des morceaux redonne le texte exact, ce qui garantit des positions justes."""
    if separator == "":
        return list(text)
    parts = text.split(separator)
    pieces = [part + separator for part in parts[:-1]]
    if parts[-1]:
        pieces.append(parts[-1])
    return pieces


class RecursiveChunker(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_size: int = Field(default=1_000, ge=1)
    """En caractères : ~250 tokens anglais. Les modèles d'embeddings ont une fenêtre
    (512 tokens pour bge, 8 191 pour text-embedding-3) ; au-delà, le texte est tronqué
    en silence par le provider."""
    chunk_overlap: int = Field(default=200, ge=0)
    separators: tuple[str, ...] = DEFAULT_SEPARATORS

    @model_validator(mode="after")
    def _overlap_smaller_than_size(self) -> "RecursiveChunker":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap doit être strictement inférieur à chunk_size")
        if not self.separators or self.separators[-1] != "":
            raise ValueError("le dernier séparateur doit être '' (découpe par caractère)")
        return self

    def describe(self) -> dict[str, str | int]:
        """Ce que le registre d'index enregistre : de quoi régénérer les mêmes chunks."""
        return {
            "chunker": "recursive",
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "separators": repr(self.separators),
        }

    def split_text(self, text: str) -> list[str]:
        return [piece for piece in self._split(text, self.separators) if piece.strip()]

    def _split(self, text: str, separators: tuple[str, ...]) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]
        separator = next(s for s in separators if s == "" or s in text)
        remaining = separators[separators.index(separator) + 1 :]
        chunks: list[str] = []
        window: list[str] = []
        length = 0
        for piece in _split_keep(text, separator):
            if len(piece) > self.chunk_size:
                if window:
                    chunks.append("".join(window))
                    window, length = [], 0
                chunks.extend(self._split(piece, remaining))
                continue
            if window and length + len(piece) > self.chunk_size:
                chunks.append("".join(window))
                while window and length > self.chunk_overlap:
                    length -= len(window.pop(0))
            window.append(piece)
            length += len(piece)
        if window:
            chunks.append("".join(window))
        return chunks

    def chunk(self, document: ParsedDocument) -> list[Chunk]:
        chunks: list[Chunk] = []
        ordinal = 0
        for section in document.sections:
            cursor = 0
            for piece in self.split_text(section.text):
                text = piece.strip()
                start = section.text.find(text, cursor)
                if start < 0:  # pragma: no cover - garde-fou, ne devrait jamais arriver
                    start = section.text.find(text)
                end = start + len(text)
                chunks.append(
                    Chunk(
                        chunk_id=f"{document.doc_id}#{ordinal:04d}",
                        doc_id=document.doc_id,
                        ordinal=ordinal,
                        text=text,
                        section_title=section.title,
                        section_order=section.order,
                        start_char=start,
                        end_char=end,
                        checksum=sha256_text(text),
                        token_estimate=estimate_tokens(text),
                    )
                )
                cursor = start + 1
                ordinal += 1
        return chunks
