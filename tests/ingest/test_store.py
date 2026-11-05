"""Tests of the pgvector storage — require a database (``db`` marker).

Locally: ``make tilt-db`` (forwards port 5432) then
``LLM_TESTBENCH_DATABASE_URL=postgresql://testbench:testbench-local-only@localhost:5432/testbench``.
"""

import os
import uuid
from collections.abc import AsyncIterator

import pytest

from llm_testbench.ingest.chunking import EmbeddingInput, RecursiveChunker
from llm_testbench.ingest.parsing import parse_text
from llm_testbench.ingest.store import IndexMismatchError, IndexSpec, PgVectorStore
from llm_testbench.llm.types import ModelRef

DATABASE_URL = os.environ.get("LLM_TESTBENCH_DATABASE_URL")

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(DATABASE_URL is None, reason="LLM_TESTBENCH_DATABASE_URL not set"),
]


@pytest.fixture
async def store() -> AsyncIterator[PgVectorStore]:
    assert DATABASE_URL is not None
    async with PgVectorStore.from_url(DATABASE_URL, max_size=2) as store:
        await store.ensure_schema()
        yield store


@pytest.fixture
def source_key() -> str:
    return f"test:{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def spec(store: PgVectorStore, source_key: str) -> AsyncIterator[IndexSpec]:
    spec = IndexSpec(
        index_key=f"t-{uuid.uuid4().hex[:8]}",
        source_key=source_key,
        embedding_model=ModelRef.parse("openai/text-embedding-3-small"),
        dimensions=3,
        chunker=RecursiveChunker(chunk_size=40, chunk_overlap=0).describe(),
        description="test index",
    )
    await store.register_index(spec)
    yield spec
    await store.drop_index(spec.index_key)
    await store.delete_source(source_key)


async def test_schema_is_idempotent(store: PgVectorStore) -> None:
    await store.ensure_schema()
    await store.ensure_schema()


async def test_register_index_is_idempotent_but_refuses_a_different_definition(
    store: PgVectorStore, spec: IndexSpec
) -> None:
    await store.register_index(spec)
    assert await store.get_index(spec.index_key) == spec
    assert spec in await store.list_indexes()
    with pytest.raises(IndexMismatchError, match=spec.index_key):
        await store.register_index(spec.model_copy(update={"dimensions": 4}))


async def test_upsert_is_a_noop_on_identical_content_and_replaces_on_change(
    store: PgVectorStore, spec: IndexSpec, source_key: str
) -> None:
    chunker = RecursiveChunker(chunk_size=40, chunk_overlap=0)
    document = parse_text("d1", "First sentence of the document. Second sentence, a little longer.")
    chunks = chunker.chunk(document)
    assert await store.upsert_document(source_key, document, chunks) is True
    assert await store.upsert_document(source_key, document, chunks) is False
    assert await store.counts(source_key) == (1, len(chunks))

    inputs = [EmbeddingInput.from_chunk(document, c) for c in chunks]
    await store.add_embeddings(spec, [(inputs[0], [1.0, 0.0, 0.0])])
    assert await store.embedding_count(spec) == 1
    assert [i.chunk.chunk_id for i in await store.missing_embeddings(spec, inputs)] == [
        c.chunk_id for c in chunks[1:]
    ]
    # Same chunks, new title: the stored vector no longer matches what would be embedded.
    retitled = document.model_copy(update={"title": "New title"})
    renamed = [EmbeddingInput.from_chunk(retitled, c) for c in chunks]
    assert len(await store.missing_embeddings(spec, renamed)) == len(chunks)

    changed = parse_text("d1", "Entirely different content.")
    new_chunks = chunker.chunk(changed)
    assert await store.upsert_document(source_key, changed, new_chunks) is True
    stored = await store.fetch_document(source_key, "d1")
    assert stored is not None
    assert [c.text for c in stored.chunks] == [c.text for c in new_chunks]
    assert await store.embedding_count(spec) == 0  # cascade: the old vectors are gone
    assert await store.fetch_document(source_key, "absent") is None


async def test_search_returns_nearest_chunks_with_cosine_scores_and_filters(
    store: PgVectorStore, spec: IndexSpec, source_key: str
) -> None:
    chunker = RecursiveChunker(chunk_size=1_000, chunk_overlap=0)
    fr, en = {"lang": "fr"}, {"lang": "en"}
    docs = {
        "a": (parse_text("a", "Document about cats.", metadata=fr), [1.0, 0.0, 0.0]),
        "b": (parse_text("b", "Document about dogs.", metadata=en), [0.0, 1.0, 0.0]),
        "c": (parse_text("c", "Another document about dogs.", metadata=fr), [0.7, 0.7, 0.0]),
    }
    for document, vector in docs.values():
        chunks = chunker.chunk(document)
        await store.upsert_document(source_key, document, chunks)
        await store.add_embeddings(spec, [(EmbeddingInput.from_chunk(document, chunks[0]), vector)])

    hits = await store.search(spec, [1.0, 0.0, 0.0], k=2)
    assert [h.chunk.doc_id for h in hits] == ["a", "c"]
    assert hits[0].score == pytest.approx(1.0, abs=1e-6)
    assert hits[1].score == pytest.approx(0.7071, abs=1e-3)
    assert hits[0].document_metadata == {"lang": "fr"}

    english = await store.search(spec, [1.0, 0.0, 0.0], k=5, filters={"lang": "en"})
    assert [h.chunk.doc_id for h in english] == ["b"]

    first = EmbeddingInput.from_chunk(docs["a"][0], chunker.chunk(docs["a"][0])[0])
    with pytest.raises(ValueError, match="dimension 2"):
        await store.add_embeddings(spec, [(first, [1.0, 0.0])])


async def test_search_documents_ranks_each_document_once_by_its_best_chunk(
    store: PgVectorStore, spec: IndexSpec, source_key: str
) -> None:
    chunker = RecursiveChunker(chunk_size=40, chunk_overlap=0)
    # "long" is cut in several chunks; one of them is the nearest to the query, another
    # the farthest. "short" has a single chunk, in between.
    long = parse_text("long", "First sentence of the document. Second sentence, a little longer.")
    short = parse_text("short", "One chunk only.")
    long_chunks, short_chunks = chunker.chunk(long), chunker.chunk(short)
    assert len(long_chunks) >= 2
    await store.upsert_document(source_key, long, long_chunks)
    await store.upsert_document(source_key, short, short_chunks)
    vectors = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]][: len(long_chunks)]
    await store.add_embeddings(
        spec,
        [
            (EmbeddingInput.from_chunk(long, chunk), vector)
            for chunk, vector in zip(long_chunks, vectors, strict=True)
        ],
    )
    await store.add_embeddings(
        spec, [(EmbeddingInput.from_chunk(short, short_chunks[0]), [0.7, 0.7, 0.0])]
    )

    for mode in ({"exact": True}, {"exact": False}, {"exact": False, "ef_search": 100}):
        hits = await store.search_documents(spec, [1.0, 0.0, 0.0], k=5, **mode)
        assert [hit.doc_id for hit in hits] == ["long", "short"]
        assert hits[0].score == pytest.approx(1.0, abs=1e-6)  # the best chunk, not the mean
        assert hits[0].chunks == len(long_chunks)
        assert hits[1].score == pytest.approx(0.7071, abs=1e-3)

    # A chunk-level search returns "long" once per chunk; the document-level one never does.
    chunk_level = [hit.chunk.doc_id for hit in await store.search(spec, [1.0, 0.0, 0.0], k=5)]
    assert chunk_level.count("long") == len(long_chunks)
    assert [hit.doc_id for hit in await store.search_documents(spec, [1.0, 0.0, 0.0], k=1)] == [
        "long"
    ]
    # Fewer candidates than chunks: only the documents of the nearest chunks are ranked.
    nearest = await store.search_documents(spec, [1.0, 0.0, 0.0], k=5, candidates=1)
    assert [hit.doc_id for hit in nearest] == ["long"]
    assert nearest[0].chunks == 1
