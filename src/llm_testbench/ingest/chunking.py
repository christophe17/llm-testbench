"""Recursive chunking by separators — the naive baseline that phase 3 must beat.

Principle: we try to cut on the most "natural" separator (paragraph), and if a piece
is still too long, we go down one notch (line, sentence, word, character). The pieces
are then grouped up to ``chunk_size`` characters, with a ``chunk_overlap`` overlap so
as not to cut an idea in two without a witness.

What makes this chunker naive, and what we will measure: it ignores structure (a table,
a list, a note), cuts long sentences in the middle, and knows nothing of the content. It
is rewritten here (rather than imported) to fit on one readable page in notebook 2.
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
    """Position in the section text (not the document): ``section.text[start:end]``."""
    end_char: int = Field(ge=0)
    checksum: str
    token_estimate: int = Field(ge=0)

    def locator(self) -> str:
        section = f'section "{self.section_title}"' if self.section_title else "text"
        return f"{section}, characters {self.start_char}–{self.end_char}"


def _split_keep(text: str, separator: str) -> list[str]:
    """Split while keeping the separator at the end of each piece: concatenating the
    pieces gives back the exact text, which guarantees correct positions."""
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
    """In characters: ~250 English tokens. Embedding models have a window (512 tokens
    for bge, 8,191 for text-embedding-3); beyond it, the text is silently truncated by
    the provider."""
    chunk_overlap: int = Field(default=200, ge=0)
    separators: tuple[str, ...] = DEFAULT_SEPARATORS

    @model_validator(mode="after")
    def _overlap_smaller_than_size(self) -> "RecursiveChunker":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be strictly smaller than chunk_size")
        if not self.separators or self.separators[-1] != "":
            raise ValueError("the last separator must be '' (split by character)")
        return self

    def describe(self) -> dict[str, str | int]:
        """What the index registry records: enough to regenerate the same chunks."""
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
                if start < 0:  # pragma: no cover - safeguard, should never happen
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
