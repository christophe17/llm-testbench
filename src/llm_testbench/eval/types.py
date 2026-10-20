"""Common types of the retrieval evaluation datasets.

The central contract of the testbench: whatever public dataset is loaded, a loader
produces a :class:`RetrievalDataset` — corpus, queries, relevance judgments (qrels) —
whose referential integrity is validated at construction. A loader that joins its
files wrongly fails here, loudly, not three phases later in a skewed retrieval
score.

Vocabulary (that of the IR literature, kept as is so that the scores are comparable
to the papers):

- *corpus*: the documents being searched;
- *queries*: the queries asked;
- *qrels* ("query relevance judgments"): for each query, the documents judged
  relevant and their relevance level (integer, 0 = not relevant).
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

# query_id -> (doc_id -> relevance level). Levels are integers >= 0;
# most BEIR datasets are binary (1), some are graded (NFCorpus: 0-2).
Qrels = dict[str, dict[str, int]]


class Document(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc_id: str
    text: str
    title: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class Query(BaseModel):
    model_config = ConfigDict(frozen=True)

    query_id: str
    text: str
    metadata: dict[str, str] = Field(default_factory=dict)


class DatasetInfo(BaseModel):
    """Identity card of a dataset: enough to trace the provenance of every number."""

    model_config = ConfigDict(frozen=True)

    key: str
    """Short identifier used everywhere in the testbench (e.g. ``beir/scifact``)."""

    name: str
    homepage: str
    license: str
    """License as displayed by the distribution source — see the verification of
    2026-08-26 in docs/: for BEIR, it is the claim of the packaging, not an upstream
    guarantee."""

    source: str
    """Where the data is actually loaded from (Hugging Face repositories, URL...)."""


class RetrievalDataset(BaseModel):
    model_config = ConfigDict(frozen=True)

    info: DatasetInfo
    split: str
    documents: tuple[Document, ...]
    queries: tuple[Query, ...]
    qrels: Qrels

    sampled: bool = False
    """True if the dataset was truncated (sample mode). A sampled dataset checks the
    mechanics; it NEVER produces a publishable number."""

    @model_validator(mode="after")
    def _check_referential_integrity(self) -> "RetrievalDataset":
        doc_ids = {d.doc_id for d in self.documents}
        query_ids = {q.query_id for q in self.queries}

        if len(doc_ids) != len(self.documents):
            raise ValueError("duplicate doc_id in the corpus")
        if len(query_ids) != len(self.queries):
            raise ValueError("duplicate query_id in the queries")

        orphan_queries = set(self.qrels) - query_ids
        if orphan_queries:
            raise ValueError(f"qrels reference missing queries: {sorted(orphan_queries)[:5]}")
        orphan_docs = {doc_id for judged in self.qrels.values() for doc_id in judged} - doc_ids
        if orphan_docs:
            raise ValueError(f"qrels reference missing documents: {sorted(orphan_docs)[:5]}")

        unjudged = query_ids - set(self.qrels)
        if unjudged:
            raise ValueError(
                f"queries without any judgment: {sorted(unjudged)[:5]} — "
                "the loader must filter out queries outside the split"
            )
        return self

    def document_by_id(self, doc_id: str) -> Document:
        try:
            return self._documents_by_id[doc_id]
        except KeyError:
            raise KeyError(f"unknown document: {doc_id!r}") from None

    def relevant_doc_ids(self, query_id: str, min_relevance: int = 1) -> set[str]:
        return {
            doc_id for doc_id, rel in self.qrels.get(query_id, {}).items() if rel >= min_relevance
        }

    @property
    def _documents_by_id(self) -> dict[str, Document]:
        # Lazy index, cached on the instance (allowed despite frozen since outside the model).
        cached: dict[str, Document] | None = self.__dict__.get("_doc_index")
        if cached is None:
            cached = {d.doc_id: d for d in self.documents}
            object.__setattr__(self, "_doc_index", cached)
        return cached

    def describe(self) -> dict[str, int | str | bool]:
        """Compact summary — what the notebook displays, what the harness will log."""
        judgments = sum(len(j) for j in self.qrels.values())
        return {
            "dataset": self.info.key,
            "split": self.split,
            "documents": len(self.documents),
            "queries": len(self.queries),
            "judgments": judgments,
            "sampled": self.sampled,
        }
