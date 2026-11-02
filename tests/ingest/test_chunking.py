from itertools import pairwise

import pytest

from llm_testbench.ingest.chunking import Chunk, EmbeddingInput, RecursiveChunker
from llm_testbench.ingest.parsing import parse_sections, parse_text

PARAGRAPHS = [
    "Retrieval looks for the useful documents. " * 6,
    "Chunking splits the documents into indexable pieces. " * 6,
    "Embeddings project the text into a vector space. " * 6,
]
TEXT = "\n\n".join(p.strip() for p in PARAGRAPHS)


def test_short_text_is_a_single_chunk() -> None:
    assert RecursiveChunker(chunk_size=100, chunk_overlap=0).split_text("short") == ["short"]
    assert RecursiveChunker().split_text("   \n  ") == []


def test_chunks_respect_size_and_prefer_paragraph_boundaries() -> None:
    # The longest paragraph is 318 characters: at 400, each paragraph fits whole.
    chunker = RecursiveChunker(chunk_size=400, chunk_overlap=0)
    pieces = chunker.split_text(TEXT)
    assert len(pieces) == 3
    assert all(len(p) <= 400 for p in pieces)
    assert [p.strip() for p in pieces] == [p.strip() for p in PARAGRAPHS]


def test_overlap_repeats_the_tail_of_the_previous_chunk() -> None:
    chunker = RecursiveChunker(chunk_size=120, chunk_overlap=40)
    pieces = chunker.split_text(PARAGRAPHS[0].strip())
    assert len(pieces) > 1
    assert all(len(p) <= 120 for p in pieces)
    for previous, following in pairwise(pieces):
        head = following[:20]
        assert head in previous, (previous, following)


def test_separators_cascade_down_to_characters() -> None:
    chunker = RecursiveChunker(chunk_size=50, chunk_overlap=0)
    pieces = chunker.split_text("x" * 130)
    assert [len(p) for p in pieces] == [50, 50, 30]
    assert "".join(pieces) == "x" * 130


def test_no_text_is_lost() -> None:
    chunker = RecursiveChunker(chunk_size=80, chunk_overlap=20)
    pieces = chunker.split_text(TEXT)
    for sentence in {s.strip() for p in PARAGRAPHS for s in p.split(". ") if s.strip()}:
        assert any(sentence in piece for piece in pieces), sentence


def test_chunk_positions_are_exact_slices_of_their_section() -> None:
    document = parse_sections(
        "doc",
        [("Intro", PARAGRAPHS[0].strip()), ("Body", TEXT)],
        title="Paper",
    )
    chunks = RecursiveChunker(chunk_size=150, chunk_overlap=30).chunk(document)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    assert chunks[0].chunk_id == "doc#0000"
    assert {c.section_title for c in chunks} == {"Intro", "Body"}
    for chunk in chunks:
        section = document.sections[chunk.section_order]
        assert section.text[chunk.start_char : chunk.end_char] == chunk.text
        assert chunk.token_estimate >= 1
        assert len(chunk.checksum) == 64
    assert 'section "Intro"' in chunks[0].locator()


def test_chunking_is_deterministic() -> None:
    document = parse_text("d", TEXT)
    chunker = RecursiveChunker(chunk_size=200, chunk_overlap=50)
    assert chunker.chunk(document) == chunker.chunk(document)


def test_invalid_configurations_are_rejected() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        RecursiveChunker(chunk_size=10, chunk_overlap=10)
    with pytest.raises(ValueError, match="last separator"):
        RecursiveChunker(separators=("\n",))


def test_describe_is_enough_to_regenerate() -> None:
    assert RecursiveChunker(chunk_size=5, chunk_overlap=1).describe() == {
        "chunker": "recursive",
        "chunk_size": 5,
        "chunk_overlap": 1,
        "separators": repr(("\n\n", "\n", ". ", " ", "")),
    }
    assert Chunk.model_fields["text"].annotation is str


def test_embedding_input_prefixes_the_document_title_like_beir() -> None:
    titled = parse_text("d", "Body of the abstract.", title="Title of the paper")
    (chunk,) = RecursiveChunker().chunk(titled)
    item = EmbeddingInput.from_chunk(titled, chunk)
    assert item.text == "Title of the paper Body of the abstract."
    assert item.chunk is chunk
    assert item.checksum != chunk.checksum  # the vector is keyed on the embedded text
    # Same chunk under another title: another vector to compute.
    renamed = parse_text("d", "Body of the abstract.", title="Another title")
    assert EmbeddingInput.from_chunk(renamed, chunk).checksum != item.checksum


def test_embedding_input_without_title_is_the_chunk_itself() -> None:
    document = parse_text("d", "Body of the abstract.")
    (chunk,) = RecursiveChunker().chunk(document)
    item = EmbeddingInput.from_chunk(document, chunk)
    assert item.text == chunk.text
    assert item.checksum == chunk.checksum
