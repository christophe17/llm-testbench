"""Assisted drafting: a model proposes questions, code checks what code can check.

Writing 80 good questions by hand takes days. A model writes 90 drafts in minutes, and
most of them are usable; the ones that are not are the reason every draft is reviewed by a
person before it measures anything (``review.py``). The division of labour:

- the **model** reads one paper (its reference text) and writes one question per requested
  kind, with a reference answer and the sentences that justify it
  (``prompts/golden_draft.md``);
- **code** checks each quoted sentence against the reference text, word for word. A model
  asked to quote will sometimes paraphrase, or quote a sentence that does not exist: a
  quote that is not found is flagged, never silently kept;
- the **reviewer** judges everything else: is the question clear, is the answer right, is
  the trap really a trap.

The drafter is not the model under test. Questions written by the generator itself would
be phrased the way it thinks, and it would find them easier than a user's.
"""

import random
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from llm_testbench.eval.golden.types import Category, Draft, Quote
from llm_testbench.eval.spend import SpendLedger
from llm_testbench.ingest.parsing import ParsedDocument
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.prompts import PromptRegistry
from llm_testbench.llm.structured import StructuredOutputs
from llm_testbench.llm.types import CompletionRequest, Message, ModelRef, Role

PROMPT_NAME = "golden_draft"


class DraftedQuestion(BaseModel):
    """One question as the model returns it. Every field is required and nothing else is
    allowed: it is what the strict structured outputs of the providers accept (a field
    with a default, or an open object, is refused with a 400)."""

    model_config = ConfigDict(extra="forbid")

    category: Category
    question: str
    answer: str
    quotes: list[str]
    note: str


class DraftedQuestions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[DraftedQuestion]


def _squash(text: str) -> str:
    return " ".join(text.split())


def locate(text: str, document: ParsedDocument) -> Quote:
    """The quote with the section it was found in, or marked as not found. Word for word,
    whitespace aside: a paraphrase is not evidence."""
    wanted = _squash(text)
    for section in document.sections:
        if wanted and wanted in _squash(section.text):
            return Quote(doc_id=document.doc_id, text=wanted, section=section.title, found=True)
    return Quote(doc_id=document.doc_id, text=wanted or text, found=False)


def paper_text(document: ParsedDocument, max_characters: int) -> str:
    """The paper as the drafter reads it: sections in order, under their titles, cut at
    the first section that would pass ``max_characters`` (the appendices go first)."""
    parts: list[str] = [f"TITLE: {document.title}"] if document.title else []
    used = 0
    for section in document.sections:
        if used + len(section.text) > max_characters and used > 0:
            break
        parts.append(f"## {section.title or 'Untitled section'}\n{section.text}")
        used += len(section.text)
    return "\n\n".join(parts)


def assign_categories(documents: int, per_document: int) -> list[tuple[Category, ...]]:
    """Which kinds to ask of each document, in rotation, so that the drafts are spread
    evenly over the taxonomy whatever the number of documents."""
    kinds = list(Category)
    return [
        tuple(kinds[(index * per_document + offset) % len(kinds)] for offset in range(per_document))
        for index in range(documents)
    ]


def pick_documents(doc_ids: Sequence[str], count: int, seed: int) -> list[str]:
    """``count`` documents drawn with a seed, in the order of the manifest."""
    if count >= len(doc_ids):
        return list(doc_ids)
    kept = set(random.Random(seed).sample(list(doc_ids), count))
    return [doc_id for doc_id in doc_ids if doc_id in kept]


class Drafter:
    def __init__(
        self,
        *,
        client: LLMClient,
        prompts: PromptRegistry,
        model: ModelRef,
        ledger: SpendLedger | None = None,
        max_characters: int = 24_000,
        max_output_tokens: int = 8_000,
    ) -> None:
        self.model = model
        self._prompts = prompts
        self._structured = StructuredOutputs(client, prompts)
        self._ledger = ledger
        self._max_characters = max_characters
        self._max_output_tokens = max_output_tokens

    async def draft(self, document: ParsedDocument, categories: Sequence[Category]) -> list[Draft]:
        """One draft per requested kind the model found material for."""
        rendered = self._prompts.render(PROMPT_NAME)
        wanted = ", ".join(category.value for category in categories)
        request = CompletionRequest(
            model=self.model,
            messages=(
                Message(role=Role.SYSTEM, content=rendered.text),
                Message(
                    role=Role.USER,
                    content=f"Question kinds requested: {wanted}\n\n"
                    f"{paper_text(document, self._max_characters)}",
                ),
            ),
            data_class=DataClass.PUBLIC,
            max_output_tokens=self._max_output_tokens,
            metadata=rendered.trace_metadata(),
        )
        if self._ledger is not None:
            self._ledger.check()
        result = await self._structured.complete(request, DraftedQuestions)
        if self._ledger is not None:
            self._ledger.charge(result.cost_usd, f"golden drafts {self.model}")
        drafts: list[Draft] = []
        seen: set[Category] = set()
        for drafted in result.value.questions:
            # One per requested kind: an extra, a repeat or an empty entry is dropped.
            if drafted.category not in categories or drafted.category in seen:
                continue
            if not drafted.question.strip():
                continue
            seen.add(drafted.category)
            unanswerable = drafted.category is Category.UNANSWERABLE
            given = paper_text(document, self._max_characters)
            drafts.append(
                Draft(
                    draft_id=f"{document.doc_id}-{drafted.category.value}",
                    doc_id=document.doc_id,
                    category=drafted.category,
                    question=_squash(drafted.question),
                    answer="" if unanswerable else _squash(drafted.answer),
                    quotes=()
                    if unanswerable
                    else tuple(locate(text, document) for text in drafted.quotes if text.strip()),
                    note=_squash(drafted.note),
                    drafted_by=str(self.model),
                    prompt_version=str(rendered.version),
                    characters_read=min(len(given), document.char_count),
                    characters_total=document.char_count,
                )
            )
        return drafts


CHECK_PROMPT = "golden_unanswerable_check"


class SecondReading(BaseModel):
    """What the checker returns for a draft marked unanswerable (strict schema)."""

    model_config = ConfigDict(extra="forbid")

    answered: bool
    answer: str
    quote: str


class UnanswerableChecker:
    """A second, cheaper model reads the **whole** paper for each draft marked
    unanswerable. The drafter saw only the beginning: an answer sitting in an appendix
    makes the draft wrong, and a reviewer cannot be asked to reread sixty pages per
    question. As for the drafter, the model's word is not taken: the passage it quotes is
    looked up in the text, and only a passage that is really there is shown to the
    reviewer."""

    def __init__(
        self,
        *,
        client: LLMClient,
        prompts: PromptRegistry,
        model: ModelRef,
        ledger: SpendLedger | None = None,
        max_output_tokens: int = 4_000,
    ) -> None:
        self.model = model
        self._prompts = prompts
        self._structured = StructuredOutputs(client, prompts)
        self._ledger = ledger
        self._max_output_tokens = max_output_tokens

    async def check(self, draft: Draft, document: ParsedDocument) -> Draft:
        if draft.answerable:
            return draft
        rendered = self._prompts.render(CHECK_PROMPT)
        request = CompletionRequest(
            model=self.model,
            messages=(
                Message(role=Role.SYSTEM, content=rendered.text),
                Message(
                    role=Role.USER,
                    content=f"Question: {draft.question}\n\n"
                    f"{paper_text(document, document.char_count + 1)}",
                ),
            ),
            data_class=DataClass.PUBLIC,
            max_output_tokens=self._max_output_tokens,
            metadata=rendered.trace_metadata(),
        )
        if self._ledger is not None:
            self._ledger.check()
        result = await self._structured.complete(request, SecondReading)
        if self._ledger is not None:
            self._ledger.charge(result.cost_usd, f"unanswerable check {self.model}")
        reading = result.value
        located = locate(reading.quote, document) if reading.answered else None
        found = located if located is not None and located.found else None
        return draft.model_copy(update={"found_elsewhere": found})
