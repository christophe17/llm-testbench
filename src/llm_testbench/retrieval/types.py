"""The retrieval contract: a question in, a ranking of **documents** out.

The evaluation datasets judge documents (BEIR qrels: query, document, relevance), while an
index stores chunks. A retriever therefore answers at the document level: one row per
document, best first, never the same document twice. How it gets there (a lexical index, a
vector index and a fold of the chunks back into documents, later a fusion of both) is its
own business, and :meth:`Retriever.describe` records it so that a score can be traced back
to what produced it.
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

Description = dict[str, str | int | float | bool | None]


class RetrievedDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc_id: str
    score: float
    """Comparable within one retriever only: a BM25 score and a cosine share no scale."""
    rank: int = Field(ge=1)


class Retrieval(BaseModel):
    """The answer to one query, with what it cost to produce."""

    model_config = ConfigDict(frozen=True)

    documents: tuple[RetrievedDocument, ...]
    cost_usd: float | None = 0.0
    """Query-time cost (embedding the question); ``None`` when a call has an unknown price."""
    timings_ms: dict[str, float] = Field(default_factory=dict)
    """Where the time went, by step (``embed``, ``search``): summed, it is the latency."""

    @property
    def doc_ids(self) -> list[str]:
        return [document.doc_id for document in self.documents]


@runtime_checkable
class Retriever(Protocol):
    def describe(self) -> Description:
        """What a run records about this retriever: enough to rebuild the same one."""
        ...

    async def retrieve(self, query: str, *, k: int) -> Retrieval:
        """The ``k`` best documents for ``query``, best first, each document once."""
        ...
