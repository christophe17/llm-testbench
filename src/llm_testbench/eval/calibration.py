"""Calibrating the judge against a human (phase 2.3): 50 items, two labels each.

The set is built from answers the system really produced, then deliberately unbalanced
back into balance. On gold context a good generator is supported and on topic nearly every
time; fifty such items would hold forty-eight "yes", and agreement on them measures nothing
(see ``eval/agreement.py``). So a share of the items is shown against **another passage**
(the answer loses its support) and another share against **another question** (the answer
stops being relevant). The human labels every item blind, without knowing which is which,
and those labels are the ground truth: the swaps only make sure both answers occur.

An item stores no dataset text, only which example its question, its passages and its
answer come from; the texts are read back from the dataset. The human labels live next to
the items, versioned: they are the one hand-made measurement of this phase.
"""

import datetime as dt
import json
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from llm_testbench.eval.agreement import Agreement, cohen_kappa
from llm_testbench.eval.generation import GenerationRun
from llm_testbench.eval.judge import Judge, Rubric, Verdict
from llm_testbench.eval.qa import QADataset, QAExample
from llm_testbench.sources.types import Evidence

CALIBRATION_DIR = Path("data") / "golden" / "judge_calibration"
ITEMS_FILE = "items.jsonl"
LABELS_FILE = "labels.jsonl"

Kind = Literal["natural", "other_passage", "other_question"]


class CalibrationItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_id: str
    dataset: str
    question_from: str
    passages_from: str
    answer_from: str
    """Example ids: whose question, whose gold passages, whose generated answer."""
    answer: str
    kind: Kind
    source_run: str


class HumanLabel(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_id: str
    groundedness: bool
    relevance: bool
    note: str = ""
    labeled_at: dt.datetime


class Material(BaseModel):
    """An item as a grader, human or model, reads it."""

    model_config = ConfigDict(frozen=True)

    question: str
    evidence: tuple[Evidence, ...]
    answer: str


def build_items(
    run: GenerationRun,
    dataset: QADataset,
    *,
    size: int = 50,
    other_passage: int = 10,
    other_question: int = 10,
    seed: int = 0,
) -> list[CalibrationItem]:
    """Draw ``size`` answered questions from a run and swap the passage or the question of
    some of them. Fewer answers than ``size``: all of them, at most a fifth swapped each way."""
    by_id = {example.example_id: example for example in dataset.examples}
    rng = random.Random(seed)
    answered = [answer for answer in run.scored() if not answer.refused]
    rng.shuffle(answered)
    answered = answered[:size]
    passages = min(other_passage, len(answered) // 5)
    questions = min(other_question, len(answered) // 5)
    drafts: list[tuple[Kind, str, str, str, str]] = []
    for position, answer in enumerate(answered):
        own = by_id[answer.example_id]
        others = [example for example in dataset.examples if example.example_id != own.example_id]
        kind: Kind = "natural"
        question_from = passages_from = own.example_id
        if position < passages and others:
            kind = "other_passage"
            passages_from = _another(own, others, rng, different_passage=True).example_id
        elif position < passages + questions and others:
            kind = "other_question"
            question_from = _another(own, others, rng, different_passage=False).example_id
        drafts.append((kind, question_from, passages_from, answer.example_id, answer.answer))
    rng.shuffle(drafts)  # the swapped items are not the first ones the human sees
    return [
        CalibrationItem(
            item_id=f"c{number:03d}",
            dataset=dataset.info.key,
            question_from=question_from,
            passages_from=passages_from,
            answer_from=answer_from,
            answer=text,
            kind=kind,
            source_run=run.run_id,
        )
        for number, (kind, question_from, passages_from, answer_from, text) in enumerate(
            drafts, start=1
        )
    ]


def _another(
    own: QAExample, others: Sequence[QAExample], rng: random.Random, *, different_passage: bool
) -> QAExample:
    """Another example, from the same article when there is one: a passage on the same
    subject that does not hold the answer is a harder case than an unrelated one."""
    own_texts = {passage.text for passage in own.passages}
    own_titles = {passage.title for passage in own.passages}
    usable = [
        example
        for example in others
        if not different_passage or own_texts.isdisjoint(p.text for p in example.passages)
    ] or list(others)
    same_article = [e for e in usable if own_titles & {p.title for p in e.passages}]
    return rng.choice(same_article or usable)


def materialize(item: CalibrationItem, dataset: QADataset) -> Material:
    by_id = {example.example_id: example for example in dataset.examples}
    return Material(
        question=by_id[item.question_from].question,
        evidence=tuple(by_id[item.passages_from].evidence(dataset.info.key)),
        answer=item.answer,
    )


def write_items(items: Sequence[CalibrationItem], directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ITEMS_FILE
    path.write_text("".join(item.model_dump_json() + "\n" for item in items), encoding="utf-8")
    return path


def read_items(directory: Path) -> list[CalibrationItem]:
    lines = (directory / ITEMS_FILE).read_text(encoding="utf-8").splitlines()
    return [CalibrationItem.model_validate_json(line) for line in lines if line.strip()]


def read_labels(directory: Path) -> dict[str, HumanLabel]:
    """The latest label of each item: relabelling an item appends a line, it erases nothing."""
    path = directory / LABELS_FILE
    if not path.is_file():
        return {}
    labels = [
        HumanLabel.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {label.item_id: label for label in labels}


def append_label(label: HumanLabel, directory: Path) -> None:
    with (directory / LABELS_FILE).open("a", encoding="utf-8") as handle:
        handle.write(label.model_dump_json() + "\n")


class JudgeAgreement(BaseModel):
    model_config = ConfigDict(frozen=True)

    judge: str
    rubric: Rubric
    agreement: Agreement
    cost_usd: float | None
    disagreements: tuple[str, ...]
    """Item ids where the judge and the human differ: the ones to read."""


class CalibrationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    created_at: dt.datetime
    items: int
    human_yes: dict[str, float]
    """Share of "yes" in the human labels, per rubric: the balance of the set."""
    judges: tuple[JudgeAgreement, ...]
    verdicts: dict[str, dict[str, dict[str, Verdict]]]
    """judge -> item id -> rubric -> verdict, justifications included."""


async def calibrate(
    items: Sequence[CalibrationItem],
    labels: dict[str, HumanLabel],
    dataset: QADataset,
    judges: Sequence[Judge],
) -> CalibrationReport:
    """Each judge grades every labelled item on both rubrics; agreement with the human."""
    labelled = [item for item in items if item.item_id in labels]
    if not labelled:
        raise ValueError("no human label yet: make eval-annotate")
    human = {
        Rubric.GROUNDEDNESS: [labels[item.item_id].groundedness for item in labelled],
        Rubric.RELEVANCE: [labels[item.item_id].relevance for item in labelled],
    }
    results: list[JudgeAgreement] = []
    verdicts: dict[str, dict[str, dict[str, Verdict]]] = {}
    for judge in judges:
        name = str(judge.model)
        verdicts[name] = {}
        given: dict[Rubric, list[Verdict]] = {rubric: [] for rubric in Rubric}
        for item in labelled:
            material = materialize(item, dataset)
            verdicts[name][item.item_id] = {}
            for rubric in Rubric:
                verdict = await judge.grade(
                    rubric,
                    question=material.question,
                    answer=material.answer,
                    evidence=material.evidence,
                )
                given[rubric].append(verdict)
                verdicts[name][item.item_id][rubric.value] = verdict
        for rubric in Rubric:
            labels_given = [verdict.label for verdict in given[rubric]]
            costs = [verdict.cost_usd for verdict in given[rubric]]
            results.append(
                JudgeAgreement(
                    judge=name,
                    rubric=rubric,
                    agreement=cohen_kappa(human[rubric], labels_given),
                    cost_usd=None if None in costs else sum(c for c in costs if c is not None),
                    disagreements=tuple(
                        item.item_id
                        for item, ours, theirs in zip(
                            labelled, human[rubric], labels_given, strict=True
                        )
                        if ours != theirs
                    ),
                )
            )
    return CalibrationReport(
        created_at=dt.datetime.now(dt.UTC),
        items=len(labelled),
        human_yes={rubric.value: sum(values) / len(values) for rubric, values in human.items()},
        judges=tuple(results),
        verdicts=verdicts,
    )


def format_calibration(report: CalibrationReport) -> str:
    balance = ", ".join(f"{rubric} {share:.0%} yes" for rubric, share in report.human_yes.items())
    lines = [
        f"{report.items} items labelled by hand ({balance})",
        f"{'judge':<28} {'rubric':<13} {'agreement':>9} {'kappa':>6} {'judge yes':>10} "
        f"{'cost':>8}  disagreements",
    ]
    for row in report.judges:
        agreement = row.agreement
        kappa = "—" if agreement.kappa is None else f"{agreement.kappa:.2f}"
        judge_yes = (agreement.both_yes + agreement.second_only) / agreement.items
        cost = "unknown" if row.cost_usd is None else f"${row.cost_usd:.3f}"
        lines.append(
            f"{row.judge:<28} {row.rubric.value:<13} {agreement.observed:>9.0%} {kappa:>6} "
            f"{judge_yes:>10.0%} {cost:>8}  {', '.join(row.disagreements) or 'none'}"
        )
    return "\n".join(lines)


def save_calibration(report: CalibrationReport, results_dir: Path) -> Path:
    path = results_dir / "calibration" / "judge_calibration.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.model_dump(mode="json"), indent=1) + "\n", encoding="utf-8")
    return path
