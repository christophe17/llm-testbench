"""Structured output: schema enforced when possible, always validated, repaired if needed.

Three scenarios, from best to worst:

1. the backend enforces the schema (``native_json_schema``): the JSON arrives compliant, the
   Pydantic validation only confirms — and catches the business validators that the
   JSON schema cannot express;
2. the backend cannot: we add the instruction to the system prompt, extract the JSON
   from the answer (models love code blocks), and validate;
3. it is invalid: we send the validation error back to the model, at most ``max_repairs``
   times, then give up with a typed error that keeps the raw text.

Each attempt is a full LLM call, traced and billed: the repair rate is
a testbench number, not an implementation detail.
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
    """Isolates the JSON of an answer: raw, in a code block, or buried in text."""
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
    """The completion that produced the valid value (the last one)."""
    attempts: int
    repairs: tuple[str, ...]
    """The validation errors encountered before getting there, in order."""


class StructuredOutputs:
    def __init__(self, client: LLMClient, prompts: PromptRegistry, *, max_repairs: int = 2) -> None:
        self._client = client
        self._prompts = prompts
        self.max_repairs = max_repairs

    def prepare(self, request: CompletionRequest, schema: type[BaseModel]) -> CompletionRequest:
        """The request as it will go out: native schema, or instruction in the system prompt."""
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
                    f"invalid structured output after {attempt} attempt(s)",
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
