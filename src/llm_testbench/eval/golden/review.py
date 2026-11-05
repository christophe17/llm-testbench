"""Reviewing the drafts by hand, in the terminal (``make golden-review``).

One draft at a time: its kind, what a good answer to that kind does, the question, the
reference answer, the quoted evidence with whether code found it in the document, and what
code already knows is wrong. Then one key. The decision is appended to ``reviews.jsonl``
as soon as it is given: the session stops anywhere and resumes; a draft can be reviewed
again later, the last decision wins.

The reviewer is the only check on what code cannot see: a question that gives its answer
away, a reference answer that is wrong, a "trap" whose premise is true after all. A golden
set nobody read is a list of model outputs graded against model outputs.
"""

import datetime as dt
import textwrap
from collections.abc import Callable, Sequence
from pathlib import Path

from llm_testbench.eval.golden.store import append_review, read_reviews
from llm_testbench.eval.golden.types import EXPECTED_BEHAVIOUR, Category, Draft, Review
from llm_testbench.generation.answer import is_refusal

RULES = """\
For each draft, decide whether it can measure a question-answering system.

  Accept when   the question stands on its own (it names what it is about), a person who
                read the document would give the reference answer, and the quotes justify it.
  Edit when     the idea is good and the wording is not: fix the question, the answer or
                the kind. An empty line keeps what is there.
  Reject when   the question can be answered without the document, has several right
                answers that the reference misses, or is not of the kind it claims.

A quote marked NOT FOUND was not copied from the document: the model paraphrased or
invented it. Check the answer against the document itself before accepting.

Keys: a accept, e edit, r reject — s skips, q stops (decisions so far are saved), ? rules.
"""

_KINDS = {category.value: category for category in Category}

NO_EVIDENCE = (
    "  None of its quotes is in the document word for word: nothing would tell the harness\n"
    "  where the answer is. Reject it (r), or edit it (e) into an unanswerable question.\n"
    "  Not recorded."
)


def _has_evidence(draft: Draft, kind: Category) -> bool:
    """A question that has an answer needs a place in the document that gives it."""
    return kind is Category.UNANSWERABLE or any(quote.found for quote in draft.quotes)


def _wrap(text: str, indent: str = "  ") -> str:
    return "\n".join(
        textwrap.fill(line, width=96, initial_indent=indent, subsequent_indent=indent)
        for line in text.splitlines()
    )


def show(draft: Draft, write: Callable[[str], None]) -> None:
    expected = EXPECTED_BEHAVIOUR[draft.category]
    write(f"KIND      {draft.category.value} — a good answer should {expected}")
    write(f"DOCUMENT  https://arxiv.org/html/{draft.doc_id}  (the text the quotes come from)")
    write(f"QUESTION\n{_wrap(draft.question)}")
    write(f"REFERENCE ANSWER\n{_wrap(draft.answer or '(none: the documents do not say)')}")
    for quote in draft.quotes:
        where = f"found in “{quote.section}”" if quote.found else "NOT FOUND in the document"
        write(f"QUOTE ({where})\n{_wrap(quote.text)}")
    if draft.note:
        write(f"NOTE\n{_wrap(draft.note)}")
    if draft.characters_read and draft.characters_total:
        share = draft.characters_read / draft.characters_total
        if share < 0.95:
            write(
                f"  the drafter read the first {draft.characters_read:,} of "
                f"{draft.characters_total:,} characters of the paper ({share:.0%})"
            )
    if draft.found_elsewhere is not None:
        write(
            f"A SECOND MODEL found this in “{draft.found_elsewhere.section}”\n"
            f"{_wrap(draft.found_elsewhere.text)}"
        )
    if draft.closed_book_answer is not None:
        if is_refusal(draft.closed_book_answer):
            write("  asked without any document, the generator said it did not know")
        else:
            verdict = "RIGHT" if draft.closed_book_correct else "not the reference answer"
            write(
                f"WITHOUT ANY DOCUMENT, the generator answered ({verdict})\n"
                f"{_wrap(draft.closed_book_answer)}"
            )
    for problem in draft.problems():
        write(f"  ! {problem}")


def _ask_key(read: Callable[[str], str], write: Callable[[str], None]) -> str:
    while True:
        answer = read("Decision [a/e/r/s/q/?] ").strip().lower()
        if answer in ("a", "e", "r", "s", "q"):
            return answer
        write(
            RULES if answer == "?" else "  a (accept), e (edit), r (reject), s (skip), q (stop), ?"
        )


def _ask_kind(read: Callable[[str], str], write: Callable[[str], None]) -> Category | None:
    while True:
        answer = read(f"Kind ({', '.join(_KINDS)}; Enter keeps): ").strip().lower()
        if not answer:
            return None
        if answer in _KINDS:
            return _KINDS[answer]
        write("  not a kind of the taxonomy")


def review(
    drafts: Sequence[Draft],
    directory: Path,
    *,
    again: bool = False,
    read: Callable[[str], str] = input,
    write: Callable[[str], None] = print,
) -> int:
    """Ask for a decision on the drafts not reviewed yet (all of them with ``again``);
    returns how many decisions were recorded."""
    done = read_reviews(directory)
    todo = [draft for draft in drafts if again or draft.draft_id not in done]
    write(RULES)
    write(
        f"{len(drafts) - len(todo)} of {len(drafts)} drafts already reviewed, {len(todo)} to go.\n"
    )
    recorded = 0
    for position, draft in enumerate(todo, start=1):
        write("─" * 98)
        write(f"Draft {draft.draft_id}  ({position} of {len(todo)})\n")
        show(draft, write)
        key = _ask_key(read, write)
        if key == "q":
            break
        if key == "s":
            continue
        now = dt.datetime.now(dt.UTC)
        if key == "a" and not _has_evidence(draft, draft.category):
            write(NO_EVIDENCE)
            key = _ask_key(read, write)
            if key == "q":
                break
            if key in ("s", "a"):
                continue
        if key == "a":
            decision = Review(draft_id=draft.draft_id, decision="accepted", reviewed_at=now)
        elif key == "r":
            reason = read("Why (Enter for none): ").strip()
            decision = Review(
                draft_id=draft.draft_id, decision="rejected", note=reason, reviewed_at=now
            )
        else:
            question = read("Question (Enter keeps): ").strip() or None
            answer = read("Reference answer (Enter keeps): ").strip() or None
            kind = _ask_kind(read, write)
            if not _has_evidence(draft, kind or draft.category):
                write(NO_EVIDENCE)
                continue
            if (question, answer, kind) == (None, None, None):
                write("  nothing changed: recorded as accepted")
                decision = Review(draft_id=draft.draft_id, decision="accepted", reviewed_at=now)
            else:
                decision = Review(
                    draft_id=draft.draft_id,
                    decision="edited",
                    question=question,
                    answer=answer,
                    category=kind if kind is not draft.category else None,
                    reviewed_at=now,
                )
        append_review(decision, directory)
        recorded += 1
    reviews = read_reviews(directory)
    kept = sum(1 for item in reviews.values() if item.decision != "rejected")
    write(
        f"\n{recorded} decisions recorded; {len(reviews)} of {len(drafts)} drafts reviewed, "
        f"{kept} kept. When you are done: make golden-freeze"
    )
    return recorded
