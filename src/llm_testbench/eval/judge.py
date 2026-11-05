"""LLM-as-judge (phase 2.3): a model grades what code cannot.

Whether an answer is *supported by its excerpts* (groundedness) or *addresses the question*
(relevance) is a reading task. A model can do it at scale, and a model can also do it badly
while sounding sure. What makes a judge usable is decided here, before any number:

- **one rubric, one question, one prompt**, versioned (``prompts/judge_*.md``): the judge is
  told what to check and what to ignore (length, style, citation markers: the known
  verbosity and format biases);
- **a discrete verdict**, yes or no: a score from 1 to 10 has no meaning two graders share;
- **the justification before the verdict**, in the output schema itself: a model that
  commits to a verdict first writes the justification that fits it;
- **a judge from another provider than the generator** (ADR 006): a model grades its own
  family's answers more kindly (self-preference);
- **the judge sees no metadata**: neither which system produced the answer nor what the
  expected verdict is.

None of this proves the judge is right. Its agreement with a human on the same items does
(``eval/calibration.py``): an uncalibrated judge is a generator of reassuring numbers.
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from llm_testbench.eval.spend import SpendLedger
from llm_testbench.generation.answer import render_context
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.prompts import PromptRegistry
from llm_testbench.llm.structured import StructuredOutputs
from llm_testbench.llm.types import CompletionRequest, Message, ModelRef, Role
from llm_testbench.sources.types import Evidence


class Rubric(StrEnum):
    GROUNDEDNESS = "groundedness"
    RELEVANCE = "relevance"


PROMPTS = {Rubric.GROUNDEDNESS: "judge_groundedness", Rubric.RELEVANCE: "judge_relevance"}


class JudgeOutput(BaseModel):
    """What the judge must return. The field order is the order of writing: the reasons,
    then the verdict."""

    model_config = ConfigDict(extra="forbid")

    justification: str = Field(min_length=1)
    verdict: Literal["yes", "no"]


class Verdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    rubric: Rubric
    label: bool
    justification: str
    judge: str
    """``backend/model`` as requested."""
    served_model: str
    prompt_version: str
    prompt_sha256: str
    """Fingerprint of the rubric template: a verdict is only comparable to verdicts given
    under the same rubric."""
    cost_usd: float | None
    latency_ms: float
    attempts: int


def render_material(
    rubric: Rubric, *, question: str, answer: str, evidence: Sequence[Evidence]
) -> str:
    """What the judge reads. Relevance is a property of the question and the answer alone:
    the excerpts are left out, so that a well-supported answer to another question does not
    look relevant."""
    parts = [f"Question:\n{question}"]
    if rubric is Rubric.GROUNDEDNESS:
        parts.append(f"Excerpts:\n{render_context(evidence)}")
    parts.append(f"Answer to grade:\n{answer}")
    return "\n\n".join(parts)


class Judge:
    def __init__(
        self,
        *,
        client: LLMClient,
        prompts: PromptRegistry,
        model: ModelRef,
        ledger: SpendLedger | None = None,
        max_output_tokens: int = 400,
    ) -> None:
        self.model = model
        self._prompts = prompts
        self._structured = StructuredOutputs(client, prompts)
        self._ledger = ledger
        self._max_output_tokens = max_output_tokens

    async def grade(
        self, rubric: Rubric, *, question: str, answer: str, evidence: Sequence[Evidence] = ()
    ) -> Verdict:
        rendered = self._prompts.render(PROMPTS[rubric])
        request = CompletionRequest(
            model=self.model,
            messages=(
                Message(role=Role.SYSTEM, content=rendered.text),
                Message(
                    role=Role.USER,
                    content=render_material(
                        rubric, question=question, answer=answer, evidence=evidence
                    ),
                ),
            ),
            data_class=DataClass.PUBLIC,
            max_output_tokens=self._max_output_tokens,
            metadata=rendered.trace_metadata(),
        )
        if self._ledger is not None:
            self._ledger.check()
        result = await self._structured.complete(request, JudgeOutput)
        if self._ledger is not None:
            self._ledger.charge(result.cost_usd, f"judge {self.model}")
        return Verdict(
            rubric=rubric,
            label=result.value.verdict == "yes",
            justification=result.value.justification,
            judge=str(self.model),
            served_model=result.completion.model,
            prompt_version=str(rendered.version),
            prompt_sha256=rendered.template_sha256,
            cost_usd=result.cost_usd,
            latency_ms=result.completion.latency_ms,
            attempts=result.attempts,
        )
