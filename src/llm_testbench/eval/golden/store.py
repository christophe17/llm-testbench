"""The golden set on disk: three files and a changelog, under ``data/golden/inhouse/``.

- ``drafts.jsonl``: what the model proposed, one question per line. Rewritten only by a
  new drafting run;
- ``reviews.jsonl``: the reviewer's decisions, appended one by one, so a review session
  can stop anywhere and an earlier decision can be overruled by a later line;
- ``questions.jsonl``: the frozen set, rebuilt from the two files above by
  :func:`freeze`. This is the only file an evaluation reads;
- ``CHANGELOG.md``: one entry per freeze. A score on the golden set is only comparable
  with a score on the same version of it.
"""

import datetime as dt
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path

from pydantic import BaseModel

from llm_testbench.eval.golden.types import Category, Draft, GoldenQuestion, Review, apply_review

GOLDEN_DIR = Path("data") / "golden" / "inhouse"
DRAFTS = "drafts.jsonl"
REVIEWS = "reviews.jsonl"
QUESTIONS = "questions.jsonl"
CHANGELOG = "CHANGELOG.md"


def _read[T: BaseModel](path: Path, model: type[T]) -> list[T]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [model.model_validate_json(line) for line in lines if line.strip()]


def _write(path: Path, rows: Iterable[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(row.model_dump_json() + "\n" for row in rows), encoding="utf-8")


def read_drafts(directory: Path) -> list[Draft]:
    return _read(directory / DRAFTS, Draft)


def write_drafts(drafts: Sequence[Draft], directory: Path) -> None:
    ids = [draft.draft_id for draft in drafts]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate draft_id")
    _write(directory / DRAFTS, drafts)


def read_reviews(directory: Path) -> dict[str, Review]:
    """draft id -> its latest review."""
    return {review.draft_id: review for review in _read(directory / REVIEWS, Review)}


def append_review(review: Review, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / REVIEWS).open("a", encoding="utf-8") as handle:
        handle.write(review.model_dump_json() + "\n")


def read_questions(directory: Path) -> list[GoldenQuestion]:
    return _read(directory / QUESTIONS, GoldenQuestion)


def freeze(
    directory: Path, *, version: str, summary: str, today: dt.date | None = None
) -> list[GoldenQuestion]:
    """Rebuild ``questions.jsonl`` from the drafts and their latest reviews, and record the
    version in the changelog. A question keeps its identifier from one freeze to the next
    (it is derived from its draft), so that scores can be compared question by question."""
    reviews = read_reviews(directory)
    questions = [
        question
        for draft in read_drafts(directory)
        if draft.draft_id in reviews
        and (question := apply_review(draft, reviews[draft.draft_id], f"g-{draft.draft_id}"))
        is not None
    ]
    if not questions:
        raise ValueError("no accepted question: nothing to freeze")
    previous = {question.question_id: question for question in read_questions(directory)}
    current = {question.question_id: question for question in questions}
    added = len(current.keys() - previous.keys())
    removed = len(previous.keys() - current.keys())
    changed = sum(1 for key in current.keys() & previous.keys() if current[key] != previous[key])
    _write(directory / QUESTIONS, questions)
    counts = Counter(question.category for question in questions)
    by_category = ", ".join(f"{counts[category]} {category.value}" for category in Category)
    entry = (
        f"## {version} — {(today or dt.date.today()).isoformat()}\n\n"
        f"{summary}\n\n"
        f"- {len(questions)} questions: {by_category}.\n"
        f"- Against the previous version: {added} added, {removed} removed, {changed} changed.\n"
        f"- Rewritten by the reviewer: {sum(1 for question in questions if question.edited)}; "
        f"drafts rejected: {len(reviews) - len(questions)}.\n"
    )
    changelog = directory / CHANGELOG
    header = "# Changelog of the in-house golden set\n\nNewest first.\n\n"
    body = changelog.read_text(encoding="utf-8").removeprefix(header) if changelog.is_file() else ""
    if f"## {version} " in body:
        raise ValueError(f"version {version} is already in the changelog")
    changelog.write_text(header + entry + ("\n" + body if body else ""), encoding="utf-8")
    return questions
