"""Sortie structurée : schéma imposé quand on peut, validée toujours, réparée au besoin.

Trois cas de figure, du meilleur au pire :

1. le backend impose le schéma (``native_json_schema``) : le JSON arrive conforme, la
   validation Pydantic ne fait que confirmer — et attrape les validateurs métier que le
   schéma JSON ne sait pas exprimer ;
2. le backend ne sait pas : on ajoute la consigne au system prompt, on extrait le JSON
   de la réponse (les modèles adorent les blocs de code), on valide ;
3. c'est invalide : on renvoie l'erreur de validation au modèle, au plus ``max_repairs``
   fois, puis on abandonne avec une erreur typée qui garde le texte brut.

Chaque tentative est un appel LLM complet, tracé et facturé : le taux de réparation est
un chiffre du banc, pas un détail d'implémentation.
"""

import json
import re
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.errors import StructuredOutputError
from llm_testbench.llm.prompts import PromptRegistry
from llm_testbench.llm.types import Completion, CompletionRequest, Message, Role

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> str:
    """Isole le JSON d'une réponse : brut, dans un bloc de code, ou noyé dans du texte."""
    candidate = text.strip()
    fenced = _FENCE.search(candidate)
    if fenced is not None:
        candidate = fenced.group(1).strip()
    try:
        json.loads(candidate)
    except json.JSONDecodeError:
        start = min((i for i in (candidate.find("{"), candidate.find("[")) if i >= 0), default=-1)
        end = max(candidate.rfind("}"), candidate.rfind("]"))
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    return candidate


@dataclass(frozen=True)
class StructuredResult[T: BaseModel]:
    value: T
    completion: Completion
    """La complétion qui a produit la valeur valide (la dernière)."""
    attempts: int
    repairs: tuple[str, ...]
    """Les erreurs de validation rencontrées avant d'y arriver, dans l'ordre."""


class StructuredOutputs:
    def __init__(self, client: LLMClient, prompts: PromptRegistry, *, max_repairs: int = 2) -> None:
        self._client = client
        self._prompts = prompts
        self.max_repairs = max_repairs

    def prepare(self, request: CompletionRequest, schema: type[BaseModel]) -> CompletionRequest:
        """La requête telle qu'elle partira : schéma natif, ou consigne dans le system."""
        json_schema = schema.model_json_schema()
        prepared = request.model_copy(update={"json_schema": json_schema})
        if self._client.native_json_schema(request.model):
            return prepared
        instruction = self._prompts.render(
            "structured_output_instruction",
            schema_json=json.dumps(json_schema, ensure_ascii=False, indent=2),
        )
        system = f"{request.system}\n\n{instruction.text}" if request.system else instruction.text
        messages = (Message(role=Role.SYSTEM, content=system), *request.turns)
        return prepared.with_messages(messages)

    async def complete[T: BaseModel](
        self, request: CompletionRequest, schema: type[T]
    ) -> StructuredResult[T]:
        current = self.prepare(request, schema)
        repairs: list[str] = []
        for attempt in range(1, self.max_repairs + 2):
            completion = await self._client.complete(current)
            try:
                value = schema.model_validate_json(extract_json(completion.text))
            except ValidationError as error:
                message = str(error)
            else:
                return StructuredResult(
                    value=value, completion=completion, attempts=attempt, repairs=tuple(repairs)
                )
            repairs.append(message)
            if attempt > self.max_repairs:
                raise StructuredOutputError(
                    f"sortie structurée invalide après {attempt} tentative(s)",
                    attempts=attempt,
                    raw_text=completion.text,
                    last_error=message,
                )
            repair = self._prompts.render("structured_output_repair", error=message)
            current = current.with_messages(
                (
                    *current.messages,
                    Message(role=Role.ASSISTANT, content=completion.text),
                    Message(role=Role.USER, content=repair.text),
                )
            )
        raise AssertionError("unreachable")  # pragma: no cover
