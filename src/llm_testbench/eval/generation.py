"""The generation runner: answers produced from the gold context, and scored.

For each question of a QA dataset the generator receives the passages a perfect retriever
would return, through the very prompt and parser the API uses
(:class:`~llm_testbench.generation.answer.AnswerBuilder`). Retrieval is out of the picture
by construction: whatever goes wrong here is the generator's doing (phase 2.1).

A run can ask some questions several times (``repeats``): a model does not give the same
answer twice, and the share of questions whose refusal flips from one run to the next is
the non-determinism phase 2.4 wants on the table before any gain is celebrated.
"""

import datetime as dt
import json
import time
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict

from llm_testbench.eval.metrics.generation import normalize_answer, score_answer
from llm_testbench.eval.qa import QADataset
from llm_testbench.eval.runs import git_state
from llm_testbench.eval.spend import SpendLedger
from llm_testbench.eval.stats import DEFAULT_RESAMPLES, bootstrap_mean
from llm_testbench.generation.answer import PROMPT_NAME, AnswerBuilder, parse_answer
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.types import ModelRef


class AnswerResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    example_id: str
    repeat: int = 0
    """0 for the run that is scored; 1, 2… for the repeats that measure stability."""
    answerable: bool
    answer: str
    refused: bool
    cited: tuple[int, ...] = ()
    unknown_citations: tuple[int, ...] = ()
    metrics: dict[str, float]
    latency_ms: float
    cost_usd: float | None
    input_tokens: int
    output_tokens: int


class RateSummary(BaseModel):
    """A mean over the examples a metric applies to, with its bootstrap interval."""

    model_config = ConfigDict(frozen=True)

    mean: float
    low: float
    high: float
    examples: int


class Stability(BaseModel):
    """What changes when the same questions are asked again."""

    model_config = ConfigDict(frozen=True)

    examples: int
    runs: int
    refusal_flips: float
    """Share of the repeated questions answered in one run and refused in another."""
    answer_changes: float
    """Share whose answers are not word for word the same across the runs."""


class GenerationRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    created_at: dt.datetime
    suite: str
    arm: str
    dataset: dict[str, int | str | bool]
    context: str = "gold passages"
    generator: str
    """``backend/model`` as requested."""
    served_models: tuple[str, ...]
    """What the provider says it served: it can differ from what was asked."""
    prompt: dict[str, str]
    sample_mode: bool = False
    metrics: dict[str, RateSummary]
    stability: Stability | None = None
    latency_ms: dict[str, float]
    cost_usd: float | None
    input_tokens: int
    output_tokens: int
    duration_s: float
    git_sha: str | None = None
    git_dirty: bool | None = None
    answers: tuple[AnswerResult, ...]

    @property
    def publishable(self) -> bool:
        return not self.sample_mode

    def scored(self) -> list[AnswerResult]:
        return [answer for answer in self.answers if answer.repeat == 0]


def _stability(answers: Sequence[AnswerResult]) -> Stability | None:
    by_example: dict[str, list[AnswerResult]] = {}
    for answer in answers:
        by_example.setdefault(answer.example_id, []).append(answer)
    repeated = [group for group in by_example.values() if len(group) > 1]
    if not repeated:
        return None
    flips = sum(1 for group in repeated if len({a.refused for a in group}) > 1)
    changes = sum(1 for group in repeated if len({normalize_answer(a.answer) for a in group}) > 1)
    return Stability(
        examples=len(repeated),
        runs=max(len(group) for group in repeated),
        refusal_flips=flips / len(repeated),
        answer_changes=changes / len(repeated),
    )


async def run_generation(
    dataset: QADataset,
    *,
    client: LLMClient,
    builder: AnswerBuilder,
    model: ModelRef,
    suite: str,
    arm: str,
    repeats: int = 1,
    repeat_examples: int = 0,
    max_output_tokens: int = 512,
    ledger: SpendLedger | None = None,
    sample_mode: bool = False,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = 0,
) -> GenerationRun:
    created_at = dt.datetime.now(dt.UTC)
    started = time.perf_counter()
    source_key = dataset.info.key
    answers: list[AnswerResult] = []
    served: list[str] = []
    prompt: dict[str, str] = {}
    cost: float | None = 0.0
    try:
        for repeat in range(max(repeats, 1)):
            examples = dataset.examples if repeat == 0 else dataset.examples[:repeat_examples]
            for example in examples:
                if ledger is not None:
                    ledger.check()
                evidence = example.evidence(source_key)
                request = builder.build_request(
                    example.question,
                    evidence,
                    model=model,
                    data_class=DataClass.PUBLIC,
                    max_output_tokens=max_output_tokens,
                )
                prompt = prompt or dict(request.metadata)
                # No cache: a repeat served from the cache would measure nothing.
                completion = await client.complete(request, use_cache=False)
                if ledger is not None:
                    ledger.charge(completion.cost_usd, f"{arm} / {completion.model}")
                parsed = parse_answer(completion.text, evidence)
                if completion.model not in served:
                    served.append(completion.model)
                cost = (
                    None
                    if cost is None or completion.cost_usd is None
                    else cost + completion.cost_usd
                )
                answers.append(
                    AnswerResult(
                        example_id=example.example_id,
                        repeat=repeat,
                        answerable=example.answerable,
                        answer=parsed.text,
                        refused=parsed.refused,
                        cited=parsed.cited_indexes,
                        unknown_citations=parsed.unknown_indexes,
                        metrics=score_answer(
                            parsed, answerable=example.answerable, references=example.answers
                        ),
                        latency_ms=completion.latency_ms,
                        cost_usd=completion.cost_usd,
                        input_tokens=completion.usage.total_input_tokens,
                        output_tokens=completion.usage.output_tokens,
                    )
                )
    finally:
        # Money spent is recorded even when the run stops on an error or on the cap.
        if ledger is not None:
            ledger.commit(f"generation {suite}/{arm}")

    scored = [answer for answer in answers if answer.repeat == 0]
    names = sorted({name for answer in scored for name in answer.metrics})
    summary: dict[str, RateSummary] = {}
    for name in names:
        values = [answer.metrics[name] for answer in scored if name in answer.metrics]
        interval = bootstrap_mean(values, resamples=resamples, seed=seed)
        summary[name] = RateSummary(
            mean=interval.mean, low=interval.low, high=interval.high, examples=len(values)
        )
    latencies = np.asarray([answer.latency_ms for answer in scored])
    sha, dirty = git_state()
    return GenerationRun(
        run_id=f"{created_at:%Y%m%dT%H%M%SZ}-{suite}-{arm}",
        created_at=created_at,
        suite=suite,
        arm=arm,
        dataset=dataset.describe(),
        generator=str(model),
        served_models=tuple(served),
        prompt={"name": PROMPT_NAME, **prompt},
        sample_mode=sample_mode,
        metrics=summary,
        stability=_stability(answers),
        latency_ms={
            "mean": float(latencies.mean()),
            "p50": float(np.percentile(latencies, 50)),
            "p95": float(np.percentile(latencies, 95)),
        },
        cost_usd=cost,
        input_tokens=sum(answer.input_tokens for answer in answers),
        output_tokens=sum(answer.output_tokens for answer in answers),
        duration_s=time.perf_counter() - started,
        git_sha=sha,
        git_dirty=dirty,
        answers=tuple(answers),
    )


LABELS = {
    "correct_refusal": "correct refusal (unanswerable)",
    "over_refusal": "over-refusal (answerable)",
    "contains_answer": "contains the reference answer",
    "answer_f1": "answer F1 (SQuAD)",
    "cited": "cites an excerpt (answered)",
    "invented_citation": "invents a citation (answered)",
}


def format_generation(run: GenerationRun) -> str:
    cost = "unknown" if run.cost_usd is None else f"${run.cost_usd:.4f}"
    flag = "" if run.publishable else "  [NOT PUBLISHABLE: sample mode]"
    lines = [
        f"{run.arm} — {run.dataset['dataset']}, {run.dataset['examples']} questions, "
        f"generator {run.generator}, context: {run.context}{flag}",
        f"{'metric':<34} {'rate':>6} {'95% interval':>16} {'n':>5}",
    ]
    for name, summary in run.metrics.items():
        lines.append(
            f"{LABELS.get(name, name):<34} {summary.mean:>6.3f} "
            f"{f'[{summary.low:.3f}, {summary.high:.3f}]':>16} {summary.examples:>5}"
        )
    if run.stability is not None:
        lines.append(
            f"asked {run.stability.runs} times ({run.stability.examples} questions): refusal "
            f"flips on {run.stability.refusal_flips:.0%}, wording changes on "
            f"{run.stability.answer_changes:.0%}"
        )
    lines.append(
        f"latency p50 {run.latency_ms['p50']:.0f} ms, p95 {run.latency_ms['p95']:.0f} ms — "
        f"cost {cost} ({run.input_tokens} input tokens, {run.output_tokens} output tokens)"
    )
    return "\n".join(lines)


def save_generation(run: GenerationRun, results_dir: Path) -> Path:
    """Same archive as the retrieval runs: the summary indented, one line per answer."""
    if not run.publishable:
        raise ValueError(f"run {run.run_id} is not publishable (sample mode): not archived")
    path = results_dir / "runs" / run.suite / f"{run.arm}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = run.model_dump(mode="json")
    answers = record.pop("answers")
    summary = json.dumps(record, indent=1, ensure_ascii=False)
    lines = ",\n".join(
        "  " + json.dumps(answer, ensure_ascii=False, separators=(",", ":")) for answer in answers
    )
    path.write_text(
        summary.removesuffix("\n}") + f',\n "answers": [\n{lines}\n ]\n}}\n', encoding="utf-8"
    )
    return path


def load_generation(path: Path) -> GenerationRun:
    return GenerationRun.model_validate_json(path.read_text(encoding="utf-8"))
