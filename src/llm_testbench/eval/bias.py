"""Bias probes for the judge (phase 2.3): a verdict must not move when only the form does.

A judge is a model reading a text, and a model reading a text is sensitive to things that
are not the question it was asked. Three are probed here, each by changing **one thing
that should not matter** in an item and grading it again:

- **verbosity**: sentences that add no claim are appended to the answer. A judge that
  likes long answers says "yes" more often;
- **format**: the citation markers are removed from the answer. The rubric says a ``[1]``
  proves nothing; a judge that treats it as proof says "no" more often once it is gone;
- **position**: the excerpts are shown in the opposite order. Nothing about what they say
  changes (groundedness only: relevance is graded without excerpts).

The number reported is the share of items whose verdict **flips**. It means nothing alone:
a judge graded twice on the very same item also flips sometimes. So the same item is graded
again unchanged (the ``repeat`` control), and a bias is only claimed when a perturbation
flips more verdicts than doing nothing does. The direction matters too: flips that cancel
out are noise, flips that all go towards "yes" are a bias.

Not probed here: **self-preference** (a judge kinder to answers of its own family). It
needs a second generator and a second judge, about a dollar, and is not paid for until the
calibration says the judge is usable at all (ADR 012).
"""

import datetime as dt
import json
import re
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from llm_testbench.eval.calibration import Material
from llm_testbench.eval.judge import Judge, Rubric
from llm_testbench.eval.stats import bootstrap_mean

_CITATION = re.compile(r"\s*\[\d+(?:\s*,\s*\d+)*\]")

PADDING = (
    " To put it plainly, that is the answer to the question as it was asked. I have tried to "
    "be as clear and as complete as possible, and I hope this is helpful."
)
"""Appended to an answer: more words, no new claim to support and no new subject."""

Perturbation = Callable[[Material], Material]


def repeat(material: Material) -> Material:
    """The control: nothing changes. What it flips is the judge's own noise."""
    return material


def padded(material: Material) -> Material:
    return material.model_copy(update={"answer": material.answer + PADDING})


def without_citations(material: Material) -> Material:
    return material.model_copy(update={"answer": _CITATION.sub("", material.answer).strip()})


def reversed_excerpts(material: Material) -> Material:
    return material.model_copy(update={"evidence": tuple(reversed(material.evidence))})


PERTURBATIONS: dict[str, tuple[str, Perturbation, tuple[Rubric, ...]]] = {
    "repeat": ("control", repeat, tuple(Rubric)),
    "padded": ("verbosity", padded, tuple(Rubric)),
    "without_citations": ("format", without_citations, tuple(Rubric)),
    "reversed_excerpts": ("position", reversed_excerpts, (Rubric.GROUNDEDNESS,)),
}
"""name -> (the bias it probes, the change, the rubrics it applies to)."""


class BiasResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    judge: str
    perturbation: str
    bias: str
    rubric: Rubric
    items: int
    """Items the change actually changed (an answer without a citation cannot lose one)."""
    flips: int
    flip_rate: float
    low: float
    high: float
    to_yes: int
    to_no: int
    """Direction of the flips: a bias pushes one way, noise both."""
    cost_usd: float | None


async def probe(
    materials: Sequence[Material], judge: Judge, names: Sequence[str] | None = None
) -> list[BiasResult]:
    """Grade every item as it is, then once per perturbation; one result per perturbation
    and rubric."""
    chosen = list(names) if names else list(PERTURBATIONS)
    unknown = [name for name in chosen if name not in PERTURBATIONS]
    if unknown:
        raise KeyError(f"unknown perturbation(s) {unknown} (known: {sorted(PERTURBATIONS)})")
    if not materials:
        raise ValueError("no item to probe")
    before: dict[Rubric, list[bool]] = {}
    for rubric in Rubric:
        before[rubric] = [
            (
                await judge.grade(rubric, question=m.question, answer=m.answer, evidence=m.evidence)
            ).label
            for m in materials
        ]
    results: list[BiasResult] = []
    for name in chosen:
        bias, change, rubrics = PERTURBATIONS[name]
        for rubric in rubrics:
            flips: list[float] = []
            to_yes = to_no = 0
            cost: float | None = 0.0
            for material, original in zip(materials, before[rubric], strict=True):
                changed = change(material)
                if changed == material and name != "repeat":
                    continue
                verdict = await judge.grade(
                    rubric,
                    question=changed.question,
                    answer=changed.answer,
                    evidence=changed.evidence,
                )
                cost = None if cost is None or verdict.cost_usd is None else cost + verdict.cost_usd
                flipped = verdict.label != original
                flips.append(float(flipped))
                to_yes += int(flipped and verdict.label)
                to_no += int(flipped and not verdict.label)
            if not flips:
                continue
            interval = bootstrap_mean(flips, resamples=2_000, seed=0)
            results.append(
                BiasResult(
                    judge=str(judge.model),
                    perturbation=name,
                    bias=bias,
                    rubric=rubric,
                    items=len(flips),
                    flips=int(sum(flips)),
                    flip_rate=interval.mean,
                    low=interval.low,
                    high=interval.high,
                    to_yes=to_yes,
                    to_no=to_no,
                    cost_usd=cost,
                )
            )
    return results


def format_bias(results: Sequence[BiasResult]) -> str:
    lines = [
        f"{'judge':<24} {'change':<18} {'probes':<10} {'rubric':<13} {'items':>5} "
        f"{'flips':>5} {'rate':>6} {'95% interval':>16}  direction"
    ]
    lines += [
        f"{row.judge:<24} {row.perturbation:<18} {row.bias:<10} {row.rubric.value:<13} "
        f"{row.items:>5} {row.flips:>5} {row.flip_rate:>6.2f} "
        f"{f'[{row.low:.2f}, {row.high:.2f}]':>16}  {row.to_yes} to yes, {row.to_no} to no"
        for row in results
    ]
    lines.append(
        "a change is a bias only if it flips more verdicts than the repeat control, one way"
    )
    return "\n".join(lines)


def save_bias(results: Sequence[BiasResult], results_dir: Path) -> Path:
    path = results_dir / "calibration" / "judge_bias.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "results": [row.model_dump(mode="json") for row in results],
    }
    path.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    return path
