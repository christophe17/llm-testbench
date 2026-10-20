"""From the context to the cited answer (ADR 007).

Three responsibilities, deliberately separate from the transport (JSON or SSE):

- **render the context**: numbered evidence, with its provenance visible, in retrieval
  order;
- **build the request** from the versioned ``chat_answer`` prompt (its fingerprint
  travels in the trace metadata);
- **parse the answer**: extract the cited numbers, match them to the evidence, spot
  invented numbers, and recognize the refusal by its sentinel sentence.

The refusal is an **exact sentence** rather than a JSON field to stay compatible with
streaming; it is a measurable choice (correct and abusive refusal rates, phase 2).
"""

import re
import unicodedata
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.prompts import PromptRegistry
from llm_testbench.llm.types import CompletionRequest, Message, ModelRef, Role
from llm_testbench.sources.types import Citation, Evidence

REFUSAL_SENTINEL = "I cannot answer this question from the provided documents."
PROMPT_NAME = "chat_answer"

_CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def _normalize(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in stripped if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", stripped.lower()).strip()


_REFUSAL_KEY = _normalize(REFUSAL_SENTINEL)


def render_context(evidence: Sequence[Evidence]) -> str:
    """The evidence as the model sees it: number, readable provenance, text."""
    blocks = []
    for index, item in enumerate(evidence, start=1):
        blocks.append(f"[{index}] {item.provenance.label()}\n{item.text}")
    return "\n\n".join(blocks) if blocks else "(no excerpts)"


class ParsedAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    refused: bool
    citations: tuple[Citation, ...] = ()
    """The evidence actually cited, in order of first appearance."""
    unknown_indexes: tuple[int, ...] = ()
    """Cited numbers that match no evidence: a citation hallucination."""

    @property
    def cited_indexes(self) -> tuple[int, ...]:
        return tuple(c.index for c in self.citations)


def is_refusal(text: str) -> bool:
    """The refusal is recognized up to accents, case and punctuation, but it must be the
    whole answer: a refusal buried in an answer is not one."""
    return _normalize(text) == _REFUSAL_KEY


def parse_answer(text: str, evidence: Sequence[Evidence]) -> ParsedAnswer:
    if is_refusal(text):
        return ParsedAnswer(text=text.strip(), refused=True)
    seen: list[int] = []
    for match in _CITATION.finditer(text):
        for raw in match.group(1).split(","):
            index = int(raw.strip())
            if index not in seen:
                seen.append(index)
    citations = tuple(
        Citation.from_evidence(index, evidence[index - 1])
        for index in seen
        if 1 <= index <= len(evidence)
    )
    unknown = tuple(index for index in seen if not 1 <= index <= len(evidence))
    return ParsedAnswer(
        text=text.strip(), refused=False, citations=citations, unknown_indexes=unknown
    )


class AnswerBuilder:
    def __init__(self, prompts: PromptRegistry, *, prompt_name: str = PROMPT_NAME) -> None:
        self._prompts = prompts
        self._prompt_name = prompt_name

    def build_request(
        self,
        question: str,
        evidence: Sequence[Evidence],
        *,
        model: ModelRef,
        data_class: DataClass,
        max_output_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> CompletionRequest:
        rendered = self._prompts.render(
            self._prompt_name,
            context=render_context(evidence),
            refusal_sentinel=REFUSAL_SENTINEL,
        )
        return CompletionRequest(
            model=model,
            messages=(
                Message(role=Role.SYSTEM, content=rendered.text),
                Message(role=Role.USER, content=question),
            ),
            data_class=data_class,
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,  # type: ignore[arg-type]
            metadata=rendered.trace_metadata(),
        )
