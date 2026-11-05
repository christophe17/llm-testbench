"""Labelling the calibration items by hand, in the terminal (``make eval-annotate``).

One item at a time: the question, the excerpts, the answer, then two questions that take a
``y`` or an ``n``. The item is written to ``labels.jsonl`` as soon as it is answered, so the
session can stop anywhere and resume. Nothing about the item is shown beyond what a judge
would read: not whether its passage or its question was swapped, not what a model thought
of it. A label given knowing the expected answer measures the labeller's obedience.
"""

import datetime as dt
import textwrap
from collections.abc import Callable, Sequence
from pathlib import Path

from llm_testbench.eval.calibration import (
    CalibrationItem,
    HumanLabel,
    append_label,
    materialize,
    read_labels,
)
from llm_testbench.eval.qa import QADataset

RULES = """\
Two questions per item, answered from what is on screen and nothing else.

  Supported?  y = every claim of the answer is stated in the excerpts, or follows directly
              from them. n = at least one claim is not there, or is contradicted.
              What you know from elsewhere does not count. A citation marker such as [1]
              is not a proof: read the excerpt.
  Relevant?   y = the answer gives the kind of thing the question asks for, about the thing
              it asks about, even partially. n = it answers something else.
              Whether the answer is right, or supported, does not count here.

Keys: y, n — s skips the item, q stops (everything answered so far is saved), ? shows this.
"""


def _wrap(text: str) -> str:
    return "\n".join(
        textwrap.fill(line, width=96, initial_indent="  ", subsequent_indent="  ")
        for line in text.splitlines()
    )


def _ask(prompt: str, read: Callable[[str], str], write: Callable[[str], None]) -> str:
    while True:
        answer = read(prompt).strip().lower()
        if answer in ("y", "n", "s", "q"):
            return answer
        write(RULES if answer == "?" else "  y, n, s (skip), q (stop) or ? (rules)")


def annotate(
    items: Sequence[CalibrationItem],
    dataset: QADataset,
    directory: Path,
    *,
    read: Callable[[str], str] = input,
    write: Callable[[str], None] = print,
) -> int:
    """Ask for the missing labels; returns how many were added."""
    done = read_labels(directory)
    todo = [item for item in items if item.item_id not in done]
    write(RULES)
    write(f"{len(done)} of {len(items)} items already labelled, {len(todo)} to go.\n")
    added = 0
    for item in todo:
        material = materialize(item, dataset)
        write("─" * 98)
        write(f"Item {item.item_id}  ({len(done) + added + 1} of {len(items)})\n")
        write(f"QUESTION\n{_wrap(material.question)}\n")
        for evidence in material.evidence:
            write(f"EXCERPT [{evidence.rank}]\n{_wrap(evidence.text)}\n")
        write(f"ANSWER\n{_wrap(material.answer)}\n")
        supported = _ask("Supported? [y/n] ", read, write)
        if supported == "q":
            break
        if supported == "s":
            continue
        relevant = _ask("Relevant?  [y/n] ", read, write)
        if relevant == "q":
            break
        if relevant == "s":
            continue
        note = read("Note (Enter for none): ").strip()
        append_label(
            HumanLabel(
                item_id=item.item_id,
                groundedness=supported == "y",
                relevance=relevant == "y",
                note=note,
                labeled_at=dt.datetime.now(dt.UTC),
            ),
            directory,
        )
        added += 1
    write(f"\n{added} labels added; {len(done) + added} of {len(items)} items labelled.")
    return added
