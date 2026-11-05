"""BM25: the lexical baseline every dense model has to beat.

BM25 ranks a document by the query words it contains: a rare word weighs more than a common
one (IDF), a repeated word weighs more but saturates (``k1``), and a long document is not
favoured for being long (``b``). No model, no GPU, no API: the index of SciFact is built in
a second. Small dense models lose to it on technical vocabulary (notebook 2: all-MiniLM-L6-v2
0.645 against 0.686), which is why it stays in every table of this testbench.

The index is ``bm25s`` (sparse matrices, in process), with the preprocessing of the
``mteb/baseline-bm25s`` reference so that our score reproduces the one measured through
``mteb``: title and text joined, lowercased, English stop words removed, Snowball stemming,
Lucene's BM25 variant. A harness-side baseline: whether BM25 also serves the API, and from
where (this index, or Postgres), is a phase 3 decision taken on measurements.
"""

import time
from collections.abc import Sequence
from typing import Any

from llm_testbench.eval.types import Document
from llm_testbench.retrieval.types import Description, Retrieval, RetrievedDocument


class BM25Retriever:
    def __init__(
        self,
        documents: Sequence[Document],
        *,
        k1: float = 1.5,
        b: float = 0.75,
        method: str = "lucene",
        stopwords: str = "en",
        stemmer_language: str = "english",
    ) -> None:
        import bm25s
        import Stemmer

        if not documents:
            raise ValueError("BM25 needs at least one document to index")
        self._k1, self._b, self._method = k1, b, method
        self._stopwords, self._stemmer_language = stopwords, stemmer_language
        self._stemmer = Stemmer.Stemmer(stemmer_language)
        self._doc_ids = [document.doc_id for document in documents]
        started = time.perf_counter()
        tokens = self._tokenize([f"{document.title}\n{document.text}" for document in documents])
        self._index: Any = bm25s.BM25(k1=k1, b=b, method=method)
        self._index.index(tokens, show_progress=False)
        self.build_seconds = time.perf_counter() - started

    def _tokenize(self, texts: list[str]) -> Any:
        import bm25s

        return bm25s.tokenize(
            texts, stopwords=self._stopwords, stemmer=self._stemmer, show_progress=False
        )

    def describe(self) -> Description:
        return {
            "retriever": "bm25",
            "implementation": "bm25s",
            "method": self._method,
            "k1": self._k1,
            "b": self._b,
            "stopwords": self._stopwords,
            "stemmer": self._stemmer_language,
            "documents": len(self._doc_ids),
        }

    async def retrieve(self, query: str, *, k: int) -> Retrieval:
        started = time.perf_counter()
        indexes, scores = self._index.retrieve(
            self._tokenize([query]), k=min(k, len(self._doc_ids)), show_progress=False
        )
        # A document that shares no word with the query scores 0: it was not retrieved, it
        # only fills the list. Keeping it would let chance into the recall.
        documents = tuple(
            RetrievedDocument(doc_id=self._doc_ids[int(index)], score=float(score), rank=rank)
            for rank, (index, score) in enumerate(zip(indexes[0], scores[0], strict=True), start=1)
            if score > 0.0
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return Retrieval(documents=documents, timings_ms={"search": elapsed_ms})
