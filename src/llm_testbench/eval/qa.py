"""Question-answering datasets: a question, the passages that should answer it, and the
reference answers — or the statement that no answer exists.

Retrieval datasets (``eval/types.py``) judge a ranking. These judge a **generated answer**,
and they come with the passages a perfect retriever would return. That is what lets
generation be measured apart from retrieval (phase 2.1): give the model the right context
and see what it does with it. If it invents an answer here, no amount of retrieval work will
fix it; if it answers well here and badly end to end, the retriever is the one to look at.

SQuAD 2.0 is the reason this type has ``answerable``: about half of its questions cannot be
answered from their paragraph, by construction. The only correct behaviour on those is to
refuse.

Two datasets also come with the documents to search (``corpus``), which is what an
**end-to-end** run needs: the same questions, but the context is whatever the retriever
finds. HotpotQA asks questions that need two paragraphs at once; QASPER asks questions about
one scientific paper, and a question carries the ``scope`` that restricts the search to
that paper.
"""

import random

from pydantic import BaseModel, ConfigDict, Field, model_validator

from llm_testbench.eval.types import DatasetInfo
from llm_testbench.ingest.parsing import ParsedDocument
from llm_testbench.sources.types import Evidence, Provenance


class Passage(BaseModel):
    model_config = ConfigDict(frozen=True)

    passage_id: str
    text: str = Field(min_length=1)
    title: str = ""
    document_id: str | None = None
    """The document of the corpus this passage is part of, when the dataset has a corpus:
    what tells a retrieved chunk of the right document from a look-alike."""


class QAExample(BaseModel):
    model_config = ConfigDict(frozen=True)

    example_id: str
    question: str = Field(min_length=1)
    passages: tuple[Passage, ...] = ()
    """The gold context: what a perfect retriever returns for this question. Empty only
    for an unanswerable question of a dataset that names no passage for it (QASPER)."""
    answers: tuple[str, ...] = ()
    """Reference answers written by annotators; several wordings of the same answer."""
    answerable: bool = True
    scope: dict[str, str] = Field(default_factory=dict)
    """Document metadata the search is restricted to in an end-to-end run (QASPER: the
    paper the question is about). Empty: the whole corpus is searched."""
    kind: str = ""
    """The dataset's own label for the question (HotpotQA: ``bridge`` or ``comparison``)."""

    @model_validator(mode="after")
    def _answers_match_the_label(self) -> "QAExample":
        if self.answerable and not self.answers:
            raise ValueError(f"{self.example_id}: answerable without a reference answer")
        if not self.answerable and self.answers:
            raise ValueError(f"{self.example_id}: unanswerable with a reference answer")
        if self.answerable and not self.passages:
            raise ValueError(f"{self.example_id}: answerable without a gold passage")
        return self

    def evidence(self, source_key: str) -> list[Evidence]:
        """The gold passages as the generator receives its context: numbered evidence,
        with a provenance, exactly what a retriever would hand over."""
        return [
            Evidence(
                text=passage.text,
                score=1.0,
                rank=rank,
                provenance=Provenance(
                    source_key=source_key,
                    document_id=passage.passage_id,
                    locator="gold passage",
                    title=passage.title or None,
                ),
            )
            for rank, passage in enumerate(self.passages, start=1)
        ]


def balanced_subsample(examples: list[QAExample], size: int, seed: int) -> list[QAExample]:
    """``size`` examples, half answerable and half not (the odd one goes to answerable),
    drawn with a seeded generator and returned in the order of the file. The two refusal
    rates are each measured on their own half; when one kind runs short, the other does
    not fill the gap."""
    rng = random.Random(seed)
    answerable = [example for example in examples if example.answerable]
    unanswerable = [example for example in examples if not example.answerable]
    half = size // 2
    chosen = rng.sample(answerable, min(size - half, len(answerable)))
    chosen += rng.sample(unanswerable, min(half, len(unanswerable)))
    kept = {example.example_id for example in chosen}
    return [example for example in examples if example.example_id in kept]


class QADataset(BaseModel):
    model_config = ConfigDict(frozen=True)

    info: DatasetInfo
    split: str
    examples: tuple[QAExample, ...] = Field(min_length=1)
    subsample_seed: int | None = None
    """Set when the examples are a random draw from the split (and which draw). A
    subsample is a legitimate measurement, with a wider interval; it is not sample mode."""
    corpus: tuple[ParsedDocument, ...] = ()
    """The documents an end-to-end run searches. Empty when the dataset only supports a
    run on the gold context (SQuAD 2.0)."""

    @model_validator(mode="after")
    def _ids_are_unique(self) -> "QADataset":
        ids = [example.example_id for example in self.examples]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate example_id")
        return self

    def describe(self) -> dict[str, int | str | bool]:
        answerable = sum(1 for example in self.examples if example.answerable)
        description: dict[str, int | str | bool] = {
            "dataset": self.info.key,
            "split": self.split,
            "examples": len(self.examples),
            "answerable": answerable,
            "unanswerable": len(self.examples) - answerable,
        }
        if self.subsample_seed is not None:
            description["subsample_seed"] = self.subsample_seed
        if self.corpus:
            description["corpus_documents"] = len(self.corpus)
        return description
