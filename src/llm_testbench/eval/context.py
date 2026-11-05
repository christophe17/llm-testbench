"""Where the generator's context comes from: the gold passages, a search, or nothing.

The same questions are asked twice. With the **gold context**, the generator receives the
passages a perfect retriever would return: what goes wrong is the generator's doing. With
the **retrieved context**, it receives what the system's own search returns
(:class:`~llm_testbench.sources.documents.DocumentSource`, the path the API serves): what
goes wrong now is the sum of both. The difference between the two runs, question by
question, is what retrieval costs — the number an end-to-end score alone cannot give.

A third provider hands over **nothing**: the closed-book probe (phase 2.5). A question the
model answers correctly without any document was not answered thanks to the documents, and
a benchmark made of such questions measures the model's memory, not the system.

For that difference to be explained and not only observed, a retrieved context is scored
against the gold passages: was each of them found? A gold passage and a retrieved chunk
are not the same piece of text (a chunk is cut by size, a passage by an annotator), so
"found" is defined on the text: a chunk of the right document that holds at least half of
the passage, in one piece.
"""

import time
from difflib import SequenceMatcher
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from llm_testbench.eval.qa import Passage, QAExample
from llm_testbench.llm.governance import DataClass
from llm_testbench.retrieval.types import Description
from llm_testbench.sources.documents import DocumentSource
from llm_testbench.sources.types import Evidence

FOUND_THRESHOLD = 0.5
"""Share of a gold passage a single chunk must hold, in one piece, to count as finding it."""


class Context(BaseModel):
    """What the generator is given for one question, and what it took to get it."""

    model_config = ConfigDict(frozen=True)

    evidence: tuple[Evidence, ...]
    cost_usd: float | None = 0.0
    latency_ms: float = 0.0


class ContextProvider(Protocol):
    retrieved: bool
    """True when the context comes from a search: there is a retrieval to score."""

    def describe(self) -> Description: ...

    def applies_to(self, example: QAExample) -> bool:
        """False for a question this provider has nothing to ask on."""
        ...

    async def context(self, example: QAExample) -> Context: ...


class GoldContext:
    retrieved = False

    def __init__(self, source_key: str) -> None:
        self._source_key = source_key

    def describe(self) -> Description:
        return {"context": "gold passages"}

    def applies_to(self, example: QAExample) -> bool:
        # A question the dataset names no passage for (QASPER's unanswerable ones).
        return bool(example.passages)

    async def context(self, example: QAExample) -> Context:
        return Context(evidence=tuple(example.evidence(self._source_key)))


class NoContext:
    """Closed book: the question alone."""

    retrieved = False

    def describe(self) -> Description:
        return {"context": "none (closed book)"}

    def applies_to(self, example: QAExample) -> bool:
        return True

    async def context(self, example: QAExample) -> Context:
        return Context(evidence=())


class RetrievedContext:
    """The ``k`` chunks the document source returns for the question, searched inside the
    example's scope when it has one."""

    retrieved = True

    def __init__(
        self,
        source: DocumentSource,
        *,
        k: int = 5,
        data_class: DataClass = DataClass.PUBLIC,
    ) -> None:
        self._source = source
        self._k = k
        self._data_class = data_class

    def applies_to(self, example: QAExample) -> bool:
        return True

    def describe(self) -> Description:
        spec = self._source.spec
        return {
            "context": "retrieved",
            "k": self._k,
            "index_key": spec.index_key,
            "embedding_model": str(spec.embedding_model),
        }

    async def context(self, example: QAExample) -> Context:
        started = time.perf_counter()
        embedding = await self._source.embed_query(example.question, self._data_class)
        evidence = await self._source.search_vector(
            embedding.vectors[0], k=self._k, filters=example.scope
        )
        return Context(
            evidence=tuple(evidence),
            cost_usd=embedding.cost_usd,
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )


def _squash(text: str) -> str:
    return " ".join(text.split())


def passage_found(
    passage: Passage, evidence: tuple[Evidence, ...], *, threshold: float = FOUND_THRESHOLD
) -> bool:
    """One retrieved chunk, from the passage's document when it names one, holds at least
    ``threshold`` of the passage as one contiguous piece (whitespace aside)."""
    wanted = _squash(passage.text)
    for item in evidence:
        if passage.document_id is not None and item.provenance.document_id != passage.document_id:
            continue
        chunk = _squash(item.text)
        if wanted in chunk:
            return True
        longest = SequenceMatcher(None, wanted, chunk, autojunk=False).find_longest_match()
        if longest.size >= threshold * len(wanted):
            return True
    return False


def score_context(example: QAExample, evidence: tuple[Evidence, ...]) -> dict[str, float]:
    """Retrieval, judged on what the generator was actually handed.

    - ``context_empty``: the search returned nothing at all;
    - ``context_recall``: share of the gold passages found (answerable questions only: an
      unanswerable question has no passage to find);
    - ``context_complete``: all of them found. For a question that needs two paragraphs,
      finding one is a failure, and a mean recall of 0.5 hides whether half the questions
      are fully served or all of them half served.
    """
    scores = {"context_empty": float(not evidence)}
    if example.answerable and example.passages:
        found = [passage_found(passage, evidence) for passage in example.passages]
        scores["context_recall"] = sum(found) / len(found)
        scores["context_complete"] = float(all(found))
    return scores
