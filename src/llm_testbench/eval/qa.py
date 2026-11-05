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
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from llm_testbench.eval.types import DatasetInfo
from llm_testbench.sources.types import Evidence, Provenance


class Passage(BaseModel):
    model_config = ConfigDict(frozen=True)

    passage_id: str
    text: str = Field(min_length=1)
    title: str = ""


class QAExample(BaseModel):
    model_config = ConfigDict(frozen=True)

    example_id: str
    question: str = Field(min_length=1)
    passages: tuple[Passage, ...] = Field(min_length=1)
    """The gold context: what a perfect retriever returns for this question."""
    answers: tuple[str, ...] = ()
    """Reference answers written by annotators; several wordings of the same answer."""
    answerable: bool = True

    @model_validator(mode="after")
    def _answers_match_the_label(self) -> "QAExample":
        if self.answerable and not self.answers:
            raise ValueError(f"{self.example_id}: answerable without a reference answer")
        if not self.answerable and self.answers:
            raise ValueError(f"{self.example_id}: unanswerable with a reference answer")
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


class QADataset(BaseModel):
    model_config = ConfigDict(frozen=True)

    info: DatasetInfo
    split: str
    examples: tuple[QAExample, ...] = Field(min_length=1)
    subsample_seed: int | None = None
    """Set when the examples are a random draw from the split (and which draw). A
    subsample is a legitimate measurement, with a wider interval; it is not sample mode."""

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
        return description
