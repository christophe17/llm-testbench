"""Postgres + pgvector storage (ADR 007).

An index = an ``emb_<key>`` table with a fixed dimension, with an HNSW index on cosine
distance, and a row in the ``indexes`` registry that says how it was produced. Documents
and chunks are shared by all the indexes of a same source: reindexing with another
embedding model re-parses nothing.

Everything goes through an async connection pool; dynamic SQL identifiers (index table
names) are composed with ``psycopg.sql``, never by concatenation.
"""

import datetime as dt
import json
import re
from collections.abc import Sequence
from importlib import resources
from types import TracebackType
from typing import Any

import numpy as np
from pgvector.psycopg import register_vector_async
from psycopg import AsyncConnection, sql
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, ConfigDict, Field

from llm_testbench.ingest.chunking import Chunk, EmbeddingInput
from llm_testbench.ingest.parsing import ParsedDocument
from llm_testbench.llm.types import ModelRef

_INDEX_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
SCHEMA_FILE = "001_schema.sql"


class IndexSpec(BaseModel):
    """What one needs to know about an index to regenerate or query it."""

    model_config = ConfigDict(frozen=True)

    index_key: str = Field(pattern=_INDEX_KEY.pattern)
    source_key: str = Field(min_length=1)
    embedding_model: ModelRef
    dimensions: int = Field(ge=1)
    chunker: dict[str, str | int]
    description: str = ""

    @property
    def table(self) -> str:
        return "emb_" + self.index_key.replace("-", "_")


class StoredDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_key: str
    doc_id: str
    title: str
    uri: str | None
    checksum: str
    metadata: dict[str, str]
    ingested_at: dt.datetime
    chunks: tuple[Chunk, ...]


class SearchHit(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk: Chunk
    score: float
    """1 - cosine distance: 1 = identical, 0 = orthogonal."""
    document_title: str
    document_uri: str | None
    document_metadata: dict[str, str]
    ingested_at: dt.datetime


class DocumentHit(BaseModel):
    """A document as ranked by its best chunk."""

    model_config = ConfigDict(frozen=True)

    doc_id: str
    score: float
    """Cosine similarity of the best chunk of the document (1 - cosine distance)."""
    chunks: int = Field(ge=1)
    """How many chunks of this document were among the candidates."""


class IndexMismatchError(ValueError):
    """An index already exists under this key with another definition."""


def _chunk_from_row(row: dict[str, Any]) -> Chunk:
    return Chunk(
        chunk_id=row["chunk_id"],
        doc_id=row["doc_id"],
        ordinal=row["ordinal"],
        text=row["text"],
        section_title=row["section_title"],
        section_order=row["section_order"],
        start_char=row["start_char"],
        end_char=row["end_char"],
        checksum=row["checksum"],
        token_estimate=row["token_estimate"],
    )


async def _configure(conn: AsyncConnection[Any]) -> None:
    await register_vector_async(conn)


class PgVectorStore:
    def __init__(
        self, pool: AsyncConnectionPool[AsyncConnection[Any]], *, url: str | None = None
    ) -> None:
        self._pool = pool
        self._url = url

    @classmethod
    def from_url(cls, url: str, *, min_size: int = 1, max_size: int = 4) -> "PgVectorStore":
        pool: AsyncConnectionPool[AsyncConnection[Any]] = AsyncConnectionPool(
            url, min_size=min_size, max_size=max_size, open=False, configure=_configure
        )
        return cls(pool, url=url)

    async def open(self) -> None:
        """Apply the schema BEFORE opening the pool: each pool connection registers the
        ``vector`` type on creation, which fails as long as the extension does not exist.
        On a fresh database (CI), the reverse order cannot work."""
        await self.ensure_schema()
        await self._pool.open()

    async def close(self) -> None:
        await self._pool.close()

    async def __aenter__(self) -> "PgVectorStore":
        await self.open()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    # ------------------------------------------------------------------ schema

    async def ensure_schema(self) -> None:
        """Idempotent. Goes through a raw connection (without the ``vector`` adapter) when the
        URL is known, to be able to create the extension itself; otherwise through the pool."""
        schema = resources.files("llm_testbench.ingest.sql").joinpath(SCHEMA_FILE).read_text()
        if self._url is not None:
            async with await AsyncConnection.connect(self._url, autocommit=True) as conn:
                await conn.execute(schema)
            return
        async with self._pool.connection() as conn:
            await conn.execute(schema)

    async def register_index(self, spec: IndexSpec) -> None:
        """Create the vector table and the HNSW index of the index, and record it in the
        registry. Idempotent if the definition is identical; refuses a different one."""
        existing = await self.get_index(spec.index_key)
        if existing is not None and existing != spec:
            raise IndexMismatchError(
                f"index {spec.index_key!r} exists with another definition: {existing!r}"
            )
        table = sql.Identifier(spec.table)
        async with self._pool.connection() as conn:
            await conn.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    " source_key text NOT NULL, chunk_id text NOT NULL, checksum text NOT NULL,"
                    " embedding vector({dim}) NOT NULL, PRIMARY KEY (source_key, chunk_id),"
                    " FOREIGN KEY (source_key, chunk_id) REFERENCES chunks (source_key, chunk_id)"
                    " ON DELETE CASCADE)"
                ).format(table=table, dim=sql.Literal(spec.dimensions))
            )
            await conn.execute(
                sql.SQL(
                    "CREATE INDEX IF NOT EXISTS {name} ON {table}"
                    " USING hnsw (embedding vector_cosine_ops)"
                ).format(name=sql.Identifier(spec.table + "_hnsw"), table=table)
            )
            await conn.execute(
                "INSERT INTO indexes (index_key, source_key, embedding_model, dimensions,"
                " chunker, description) VALUES (%s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (index_key) DO NOTHING",
                (
                    spec.index_key,
                    spec.source_key,
                    str(spec.embedding_model),
                    spec.dimensions,
                    json.dumps(spec.chunker),
                    spec.description,
                ),
            )

    async def get_index(self, index_key: str) -> IndexSpec | None:
        async with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM indexes WHERE index_key = %s", (index_key,))
            row = await cur.fetchone()
        if row is None:
            return None
        return IndexSpec(
            index_key=row["index_key"],
            source_key=row["source_key"],
            embedding_model=ModelRef.parse(row["embedding_model"]),
            dimensions=row["dimensions"],
            chunker=row["chunker"],
            description=row["description"],
        )

    async def list_indexes(self) -> list[IndexSpec]:
        async with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT index_key FROM indexes ORDER BY created_at")
            keys = [row["index_key"] for row in await cur.fetchall()]
        specs = [await self.get_index(key) for key in keys]
        return [spec for spec in specs if spec is not None]

    async def drop_index(self, index_key: str) -> None:
        spec = await self.get_index(index_key)
        if spec is None:
            return
        async with self._pool.connection() as conn:
            drop = sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(spec.table))
            await conn.execute(drop)
            await conn.execute("DELETE FROM indexes WHERE index_key = %s", (index_key,))

    # ------------------------------------------------------------------ documents

    async def document_checksum(self, source_key: str, doc_id: str) -> str | None:
        async with self._pool.connection() as conn:
            row = await (
                await conn.execute(
                    "SELECT checksum FROM documents WHERE source_key = %s AND doc_id = %s",
                    (source_key, doc_id),
                )
            ).fetchone()
        return None if row is None else str(row[0])

    async def document_checksums(self, source_key: str) -> dict[str, str]:
        """doc_id -> fingerprint for a whole source, in one query: what lets the pipeline
        skip the unchanged documents without a round trip per document."""
        async with self._pool.connection() as conn:
            rows = await (
                await conn.execute(
                    "SELECT doc_id, checksum FROM documents WHERE source_key = %s", (source_key,)
                )
            ).fetchall()
        return {str(doc_id): str(checksum) for doc_id, checksum in rows}

    async def upsert_document(
        self, source_key: str, document: ParsedDocument, chunks: Sequence[Chunk]
    ) -> bool:
        """Write the document and its chunks. Returns True if something changed (new
        document or modified content); identical content is a no-op that keeps the
        existing embeddings."""
        if await self.document_checksum(source_key, document.doc_id) == document.checksum:
            return False
        async with self._pool.connection() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO documents (source_key, doc_id, title, uri, checksum, char_count,"
                " metadata) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (source_key, doc_id) DO UPDATE SET title = EXCLUDED.title,"
                " uri = EXCLUDED.uri, checksum = EXCLUDED.checksum,"
                " char_count = EXCLUDED.char_count, metadata = EXCLUDED.metadata,"
                " ingested_at = now()",
                (
                    source_key,
                    document.doc_id,
                    document.title,
                    document.source_uri,
                    document.checksum,
                    document.char_count,
                    json.dumps(document.metadata),
                ),
            )
            # The content changed: the old chunks (and their vectors, by cascade) go away.
            await conn.execute(
                "DELETE FROM chunks WHERE source_key = %s AND doc_id = %s",
                (source_key, document.doc_id),
            )
            async with conn.cursor() as cur:
                await cur.executemany(
                    "INSERT INTO chunks (source_key, chunk_id, doc_id, ordinal, section_title,"
                    " section_order, start_char, end_char, text, checksum, token_estimate)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    [
                        (
                            source_key,
                            c.chunk_id,
                            c.doc_id,
                            c.ordinal,
                            c.section_title,
                            c.section_order,
                            c.start_char,
                            c.end_char,
                            c.text,
                            c.checksum,
                            c.token_estimate,
                        )
                        for c in chunks
                    ],
                )
        return True

    async def fetch_document(self, source_key: str, doc_id: str) -> StoredDocument | None:
        async with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM documents WHERE source_key = %s AND doc_id = %s",
                (source_key, doc_id),
            )
            document = await cur.fetchone()
            if document is None:
                return None
            await cur.execute(
                "SELECT * FROM chunks WHERE source_key = %s AND doc_id = %s ORDER BY ordinal",
                (source_key, doc_id),
            )
            chunk_rows = await cur.fetchall()
        return StoredDocument(
            source_key=source_key,
            doc_id=doc_id,
            title=document["title"],
            uri=document["uri"],
            checksum=document["checksum"],
            metadata=document["metadata"],
            ingested_at=document["ingested_at"],
            chunks=tuple(_chunk_from_row(row) for row in chunk_rows),
        )

    async def delete_source(self, source_key: str) -> None:
        """Full cleanup of a source: documents, chunks and vectors (cascade)."""
        async with self._pool.connection() as conn:
            await conn.execute("DELETE FROM documents WHERE source_key = %s", (source_key,))

    async def counts(self, source_key: str) -> tuple[int, int]:
        async with self._pool.connection() as conn:
            docs = await (
                await conn.execute(
                    "SELECT count(*) FROM documents WHERE source_key = %s", (source_key,)
                )
            ).fetchone()
            chunks = await (
                await conn.execute(
                    "SELECT count(*) FROM chunks WHERE source_key = %s", (source_key,)
                )
            ).fetchone()
        return (int(docs[0]) if docs else 0, int(chunks[0]) if chunks else 0)

    # ------------------------------------------------------------------ vectors

    async def missing_embeddings(
        self, spec: IndexSpec, inputs: Sequence[EmbeddingInput]
    ) -> list[EmbeddingInput]:
        """The inputs that do not yet have a vector in this index — or whose embedded text
        has changed since (different fingerprint: the chunk, or the document title). This
        is the idempotence: we never pay twice for an embedding already computed."""
        if not inputs:
            return []
        query = sql.SQL(
            "SELECT chunk_id, checksum FROM {} WHERE source_key = %s AND chunk_id = ANY(%s)"
        ).format(sql.Identifier(spec.table))
        chunk_ids = [item.chunk.chunk_id for item in inputs]
        async with self._pool.connection() as conn:
            rows = await (await conn.execute(query, (spec.source_key, chunk_ids))).fetchall()
        present = {str(chunk_id): str(checksum) for chunk_id, checksum in rows}
        return [item for item in inputs if present.get(item.chunk.chunk_id) != item.checksum]

    async def embedding_checksums(self, spec: IndexSpec) -> dict[str, str]:
        """chunk_id -> fingerprint of the text embedded, for a whole index, in one query."""
        query = sql.SQL("SELECT chunk_id, checksum FROM {} WHERE source_key = %s").format(
            sql.Identifier(spec.table)
        )
        async with self._pool.connection() as conn:
            rows = await (await conn.execute(query, (spec.source_key,))).fetchall()
        return {str(chunk_id): str(checksum) for chunk_id, checksum in rows}

    async def add_embeddings(
        self, spec: IndexSpec, rows: Sequence[tuple[EmbeddingInput, Sequence[float]]]
    ) -> None:
        if not rows:
            return
        for _item, vector in rows:
            if len(vector) != spec.dimensions:
                raise ValueError(
                    f"vector of dimension {len(vector)} for index {spec.index_key!r} "
                    f"({spec.dimensions})"
                )
        query = sql.SQL(
            "INSERT INTO {} (source_key, chunk_id, checksum, embedding) VALUES (%s, %s, %s, %s)"
            " ON CONFLICT (source_key, chunk_id) DO UPDATE SET checksum = EXCLUDED.checksum,"
            " embedding = EXCLUDED.embedding"
        ).format(sql.Identifier(spec.table))
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.executemany(
                query,
                [
                    (
                        spec.source_key,
                        item.chunk.chunk_id,
                        item.checksum,
                        np.asarray(vector, dtype=np.float32),
                    )
                    for item, vector in rows
                ],
            )

    async def embedding_count(self, spec: IndexSpec) -> int:
        query = sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(spec.table))
        async with self._pool.connection() as conn:
            row = await (await conn.execute(query)).fetchone()
        return int(row[0]) if row else 0

    async def search(
        self,
        spec: IndexSpec,
        vector: Sequence[float],
        *,
        k: int = 5,
        filters: dict[str, str] | None = None,
    ) -> list[SearchHit]:
        """The ``k`` nearest chunks by cosine, with their document. The filters apply to
        the document metadata (JSON containment)."""
        needle = np.asarray(vector, dtype=np.float32)
        query = sql.SQL(
            "SELECT c.*, d.title AS document_title, d.uri AS document_uri,"
            " d.metadata AS document_metadata, d.ingested_at,"
            " 1 - (e.embedding <=> %(v)s) AS score"
            " FROM {} e"
            " JOIN chunks c ON c.source_key = e.source_key AND c.chunk_id = e.chunk_id"
            " JOIN documents d ON d.source_key = c.source_key AND d.doc_id = c.doc_id"
            " WHERE e.source_key = %(source)s AND d.metadata @> %(filters)s"
            " ORDER BY e.embedding <=> %(v)s LIMIT %(k)s"
        ).format(sql.Identifier(spec.table))
        params = {
            "v": needle,
            "source": spec.source_key,
            "filters": json.dumps(filters or {}),
            "k": k,
        }
        async with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()
        return [
            SearchHit(
                chunk=_chunk_from_row(row),
                score=float(row["score"]),
                document_title=row["document_title"],
                document_uri=row["document_uri"],
                document_metadata=row["document_metadata"],
                ingested_at=row["ingested_at"],
            )
            for row in rows
        ]

    async def search_documents(
        self,
        spec: IndexSpec,
        vector: Sequence[float],
        *,
        k: int = 10,
        exact: bool = False,
        ef_search: int | None = None,
        candidates: int | None = None,
    ) -> list[DocumentHit]:
        """The ``k`` best **documents**, each ranked by its best chunk ("MaxP").

        The index stores chunks, the evaluation datasets judge documents: the nearest
        chunks are folded back into documents, a document keeping the score of its best
        chunk. Two ways to find the nearest chunks, and the harness measures both:

        - ``exact=True``: the index is switched off for the query and every vector is
          compared. Slow at scale, but it is the truth the index approximates, and what a
          published score assumes;
        - otherwise the HNSW index answers. It explores a bounded list of candidates
          (``hnsw.ef_search``, 40 by default in pgvector) and **never returns more rows
          than that list holds**, whatever the ``LIMIT``: asking for 100 chunks with the
          default setting returns 40, without an error. ``ef_search`` raises the bound
          (1,000 at most), at the price of latency.

        ``candidates`` is the number of nearest chunks folded into documents (default
        ``4 * k``; ignored when ``exact``, where every chunk is a candidate).
        """
        needle = np.asarray(vector, dtype=np.float32)
        query = sql.SQL(
            "SELECT doc_id, max(score) AS score, count(*) AS chunks FROM ("
            " SELECT c.doc_id, 1 - (e.embedding <=> %(v)s) AS score"
            " FROM {} e"
            " JOIN chunks c ON c.source_key = e.source_key AND c.chunk_id = e.chunk_id"
            " WHERE e.source_key = %(source)s"
            " ORDER BY e.embedding <=> %(v)s LIMIT %(candidates)s"
            ") nearest GROUP BY doc_id ORDER BY score DESC, doc_id LIMIT %(k)s"
        ).format(sql.Identifier(spec.table))
        params = {
            "v": needle,
            "source": spec.source_key,
            "candidates": None if exact else (candidates or 4 * k),
            "k": k,
        }
        # SET LOCAL lives and dies with the transaction: the pooled connection goes back
        # to the pool with its default settings.
        async with self._pool.connection() as conn, conn.transaction():
            if exact:
                await conn.execute("SET LOCAL enable_indexscan = off")
            elif ef_search is not None:
                await conn.execute(
                    sql.SQL("SET LOCAL hnsw.ef_search = {}").format(sql.Literal(ef_search))
                )
            rows = await (await conn.execute(query, params)).fetchall()
        return [
            DocumentHit(doc_id=str(doc_id), score=float(score), chunks=int(chunks))
            for doc_id, score, chunks in rows
        ]
