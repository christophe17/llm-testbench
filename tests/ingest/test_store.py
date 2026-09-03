"""Tests du stockage pgvector — exigent une base (marqueur ``db``).

Localement : ``make k3d-up`` + ``make pg-port-forward`` puis
``LLM_TESTBENCH_DATABASE_URL=postgresql://testbench:testbench-local-only@localhost:5432/testbench``.
"""

import os
import uuid
from collections.abc import AsyncIterator

import pytest

from llm_testbench.ingest.chunking import RecursiveChunker
from llm_testbench.ingest.parsing import parse_text
from llm_testbench.ingest.store import IndexMismatchError, IndexSpec, PgVectorStore
from llm_testbench.llm.types import ModelRef

DATABASE_URL = os.environ.get("LLM_TESTBENCH_DATABASE_URL")

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(DATABASE_URL is None, reason="LLM_TESTBENCH_DATABASE_URL non défini"),
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
        description="index de test",
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
    document = parse_text("d1", "Première phrase du document. Seconde phrase, un peu plus longue.")
    chunks = chunker.chunk(document)
    assert await store.upsert_document(source_key, document, chunks) is True
    assert await store.upsert_document(source_key, document, chunks) is False
    assert await store.counts(source_key) == (1, len(chunks))

    await store.add_embeddings(spec, [(chunks[0], [1.0, 0.0, 0.0])])
    assert await store.embedding_count(spec) == 1
    assert [c.chunk_id for c in await store.missing_embeddings(spec, chunks)] == [
        c.chunk_id for c in chunks[1:]
    ]

    changed = parse_text("d1", "Un contenu entièrement différent.")
    new_chunks = chunker.chunk(changed)
    assert await store.upsert_document(source_key, changed, new_chunks) is True
    stored = await store.fetch_document(source_key, "d1")
    assert stored is not None
    assert [c.text for c in stored.chunks] == [c.text for c in new_chunks]
    assert await store.embedding_count(spec) == 0  # cascade : les anciens vecteurs sont partis
    assert await store.fetch_document(source_key, "absent") is None


async def test_search_returns_nearest_chunks_with_cosine_scores_and_filters(
    store: PgVectorStore, spec: IndexSpec, source_key: str
) -> None:
    chunker = RecursiveChunker(chunk_size=1_000, chunk_overlap=0)
    fr, en = {"lang": "fr"}, {"lang": "en"}
    docs = {
        "a": (parse_text("a", "Document sur les chats.", metadata=fr), [1.0, 0.0, 0.0]),
        "b": (parse_text("b", "Document about dogs.", metadata=en), [0.0, 1.0, 0.0]),
        "c": (parse_text("c", "Document sur les chiens.", metadata=fr), [0.7, 0.7, 0.0]),
    }
    for document, vector in docs.values():
        chunks = chunker.chunk(document)
        await store.upsert_document(source_key, document, chunks)
        await store.add_embeddings(spec, [(chunks[0], vector)])

    hits = await store.search(spec, [1.0, 0.0, 0.0], k=2)
    assert [h.chunk.doc_id for h in hits] == ["a", "c"]
    assert hits[0].score == pytest.approx(1.0, abs=1e-6)
    assert hits[1].score == pytest.approx(0.7071, abs=1e-3)
    assert hits[0].document_metadata == {"lang": "fr"}

    english = await store.search(spec, [1.0, 0.0, 0.0], k=5, filters={"lang": "en"})
    assert [h.chunk.doc_id for h in english] == ["b"]

    with pytest.raises(ValueError, match="dimension 2"):
        await store.add_embeddings(spec, [(chunker.chunk(docs["a"][0])[0], [1.0, 0.0])])
