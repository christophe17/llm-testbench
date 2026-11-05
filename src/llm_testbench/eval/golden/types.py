"""A golden question: what is asked, what the right answer is, and where the documents
say so.

Public datasets give thousands of questions; they cannot say whether the system works on
*these* documents, and a model may have read them during training. A golden set is the
small evaluation written for one corpus. Its value is not its size (50 to 80 questions) but
what each question is known to be: its kind, its reference answer, and the exact sentences
of the documents that justify the answer, checked by a person.

The taxonomy is the point of the exercise. A set made only of "what is X?" questions says
nothing about the failures that matter in production:

- ``factual``: one fact, stated in one place;
- ``multi_hop``: needs two passages, in different sections or documents; one is not enough;
- ``unanswerable``: plausible, on topic, and the documents do not contain the answer. The
  right behaviour is the refusal;
- ``ambiguous``: two readings, and the documents answer them differently. The right
  behaviour is to say so, or to give both;
- ``trap``: the question assumes something false. The right behaviour is to correct it;
- ``temporal``: needs reasoning over dates the documents state (which came first, how long
  between), not the freshness of an index.

A question goes through three states, in three files (``store.py``): a **draft** written by
a model, a **review** by a person (accept, edit, reject), and the **frozen set** that an
evaluation reads, versioned with a changelog.
"""

import datetime as dt
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Category(StrEnum):
    FACTUAL = "factual"
    MULTI_HOP = "multi_hop"
    UNANSWERABLE = "unanswerable"
    AMBIGUOUS = "ambiguous"
    TRAP = "trap"
    TEMPORAL = "temporal"


EXPECTED_BEHAVIOUR: dict[Category, str] = {
    Category.FACTUAL: "give the fact",
    Category.MULTI_HOP: "combine both passages",
    Category.UNANSWERABLE: "refuse: the documents do not say",
    Category.AMBIGUOUS: "name the two readings, or answer both",
    Category.TRAP: "correct the false premise",
    Category.TEMPORAL: "reason over the dates stated",
}


class Quote(BaseModel):
    """A sentence or two copied from a document: the evidence for the answer."""

    model_config = ConfigDict(frozen=True)

    doc_id: str
    text: str = Field(min_length=1)
    section: str = ""
    """Title of the section of the reference text the quote was found in; empty when it
    was not found (the model paraphrased, or invented)."""
    found: bool = False
    """The quote is in the reference text of the document, word for word (whitespace
    aside). Checked by code when the draft is written, never taken from the model."""


class Draft(BaseModel):
    """A question as a model proposed it. Never used for a measurement."""

    model_config = ConfigDict(frozen=True)

    draft_id: str
    doc_id: str
    category: Category
    question: str = Field(min_length=1)
    answer: str = ""
    """The reference answer; for ``unanswerable``, empty."""
    quotes: tuple[Quote, ...] = ()
    note: str = ""
    """What makes it a trap, which readings are possible, what is missing."""
    drafted_by: str
    prompt_version: str
    closed_book_answer: str | None = None
    """What a model answers without any document, when the probe was run on the draft. A
    right answer here means the question can be guessed: it does not test the system."""
    closed_book_correct: bool | None = None
    characters_read: int | None = None
    characters_total: int | None = None
    """How much of the paper the drafter was given: an "unanswerable" claim made on the
    first third of a paper says nothing about its appendices."""
    found_elsewhere: Quote | None = None
    """For a draft marked unanswerable: a passage of the whole paper that a second model
    says answers the question, when it found one and the passage is really there."""

    @property
    def answerable(self) -> bool:
        return self.category is not Category.UNANSWERABLE

    def problems(self) -> list[str]:
        """What code can tell is wrong with a draft, shown to the reviewer."""
        found: list[str] = []
        if self.answerable and not self.answer.strip():
            found.append("no reference answer")
        if self.answerable and not self.quotes:
            found.append("no evidence quoted")
        missing = sum(1 for quote in self.quotes if not quote.found)
        if missing:
            found.append(f"{missing} quote(s) not found in the document")
        sections = {quote.section for quote in self.quotes if quote.found}
        if self.category is Category.MULTI_HOP and len(sections) < 2:
            found.append("multi-hop, but the quotes found come from fewer than two sections")
        if self.closed_book_correct:
            found.append("answered correctly without any document: guessable")
        if self.found_elsewhere is not None:
            found.append("marked unanswerable, but the paper may answer it (passage below)")
        return found


Decision = Literal["accepted", "edited", "rejected"]


class Review(BaseModel):
    """A person's decision on a draft. Appended, never rewritten: the last one wins."""

    model_config = ConfigDict(frozen=True)

    draft_id: str
    decision: Decision
    question: str | None = None
    answer: str | None = None
    category: Category | None = None
    """Set when the reviewer changed them (``edited``)."""
    note: str = ""
    reviewed_at: dt.datetime

    @model_validator(mode="after")
    def _an_edit_changes_something(self) -> "Review":
        changed = (self.question, self.answer, self.category) != (None, None, None)
        if self.decision == "edited" and not changed:
            raise ValueError(f"{self.draft_id}: edited, but nothing was changed")
        if self.decision != "edited" and changed:
            raise ValueError(f"{self.draft_id}: a change needs the decision 'edited'")
        return self


class GoldenQuestion(BaseModel):
    """A reviewed question of the frozen set: what an evaluation reads."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    category: Category
    question: str
    answer: str = ""
    answerable: bool
    doc_id: str
    quotes: tuple[Quote, ...] = ()
    note: str = ""
    draft_id: str
    edited: bool = False
    """The reviewer rewrote the question, the answer or the category."""


def apply_review(draft: Draft, review: Review, question_id: str) -> GoldenQuestion | None:
    """The golden question a reviewed draft becomes; ``None`` when it was rejected."""
    if review.draft_id != draft.draft_id:
        raise ValueError(f"review of {review.draft_id} applied to {draft.draft_id}")
    if review.decision == "rejected":
        return None
    category = review.category or draft.category
    answerable = category is not Category.UNANSWERABLE
    return GoldenQuestion(
        question_id=question_id,
        category=category,
        question=review.question or draft.question,
        answer=(review.answer if review.answer is not None else draft.answer) if answerable else "",
        answerable=answerable,
        doc_id=draft.doc_id,
        quotes=draft.quotes,
        note=review.note or draft.note,
        draft_id=draft.draft_id,
        edited=review.decision == "edited",
    )
