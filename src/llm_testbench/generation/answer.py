"""Du contexte à la réponse citée (ADR 007).

Trois responsabilités, volontairement séparées du transport (JSON ou SSE) :

- **rendre le contexte** : des preuves numérotées, avec leur provenance visible, dans
  l'ordre du retrieval ;
- **construire la requête** à partir du prompt versionné ``chat_answer`` (son empreinte
  voyage dans les métadonnées de trace) ;
- **parser la réponse** : extraire les numéros cités, les rapprocher des preuves,
  repérer les numéros inventés, et reconnaître le refus par sa phrase-sentinelle.

Le refus est une **phrase exacte** plutôt qu'un champ JSON pour rester compatible avec
le streaming ; c'est un choix mesurable (taux de refus correct et abusif, phase 2).
"""

import re
import unicodedata
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.prompts import PromptRegistry
from llm_testbench.llm.types import CompletionRequest, Message, ModelRef, Role
from llm_testbench.sources.types import Citation, Evidence

REFUSAL_SENTINEL = "Je ne peux pas répondre à cette question à partir des documents fournis."
PROMPT_NAME = "chat_answer"

_CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def _normalize(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in stripped if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", stripped.lower()).strip()


_REFUSAL_KEY = _normalize(REFUSAL_SENTINEL)


def render_context(evidence: Sequence[Evidence]) -> str:
    """Les preuves telles que le modèle les voit : numéro, provenance lisible, texte."""
    blocks = []
    for index, item in enumerate(evidence, start=1):
        blocks.append(f"[{index}] {item.provenance.label()}\n{item.text}")
    return "\n\n".join(blocks) if blocks else "(aucun extrait)"


class ParsedAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    refused: bool
    citations: tuple[Citation, ...] = ()
    """Les preuves effectivement citées, dans l'ordre de première apparition."""
    unknown_indexes: tuple[int, ...] = ()
    """Numéros cités qui ne correspondent à aucune preuve : une hallucination de citation."""

    @property
    def cited_indexes(self) -> tuple[int, ...]:
        return tuple(c.index for c in self.citations)


def is_refusal(text: str) -> bool:
    """Le refus est reconnu à l'accent, à la casse et à la ponctuation près, mais il doit
    être la réponse entière : un refus noyé dans une réponse n'en est pas un."""
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
