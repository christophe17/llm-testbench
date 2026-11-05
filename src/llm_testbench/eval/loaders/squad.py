"""SQuAD 2.0 loader: questions on a Wikipedia paragraph, half of them unanswerable.

Verified on 2026-08-26: ``rajpurkar/squad_v2`` on Hugging Face, native Parquet,
CC BY-SA 4.0. The test answers are hidden, so the ``validation`` split is the evaluation
set (11,873 questions, 5,945 unanswerable, 35 articles). There is no "unanswerable" flag:
a question is unanswerable when its list of answers is empty.

A subsample is drawn half answerable, half unanswerable, with a seed: the two refusal
rates of phase 2 are each measured on their own half, and the same seed gives the same
questions on every machine.
"""

import json
from typing import Any

from llm_testbench.config import Settings, get_settings
from llm_testbench.eval.qa import Passage, QADataset, QAExample, balanced_subsample
from llm_testbench.eval.types import DatasetInfo

SQUAD_V2_INFO = DatasetInfo(
    key="squad_v2",
    name="SQuAD 2.0",
    homepage="https://rajpurkar.github.io/SQuAD-explorer/",
    license="cc-by-sa-4.0 (label of the HF repository)",
    source="hf:rajpurkar/squad_v2",
)

Row = dict[str, Any]


class SquadV2Loader:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings if settings is not None else get_settings()

    @property
    def info(self) -> DatasetInfo:
        return SQUAD_V2_INFO

    def load(
        self, split: str = "validation", *, max_examples: int | None = None, seed: int = 0
    ) -> QADataset:
        rows = self._rows(split)
        examples = [_example(row) for row in rows]
        subsample_seed: int | None = None
        if max_examples is not None and len(examples) > max_examples:
            examples = balanced_subsample(examples, max_examples, seed)
            subsample_seed = seed
        return QADataset(
            info=self.info, split=split, examples=tuple(examples), subsample_seed=subsample_seed
        )

    def _rows(self, split: str) -> list[Row]:
        fixtures_dir = self._settings.fixtures_dir
        if fixtures_dir is not None:
            path = fixtures_dir / "squad_v2" / f"{split}.json"
            if not path.is_file():
                raise FileNotFoundError(f"missing fixture: {path}")
            rows: list[Row] = json.loads(path.read_text(encoding="utf-8"))
            return rows
        from datasets import load_dataset

        cache_dir = str(self._settings.data_dir / "hf")
        return list(load_dataset("rajpurkar/squad_v2", split=split, cache_dir=cache_dir))


def _example(row: Row) -> QAExample:
    # The same answer is often given by several annotators: one copy of each wording.
    answers = tuple(dict.fromkeys(text.strip() for text in row["answers"]["text"] if text.strip()))
    return QAExample(
        example_id=str(row["id"]),
        question=row["question"].strip(),
        passages=(
            Passage(passage_id=f"{row['id']}#context", title=row["title"], text=row["context"]),
        ),
        answers=answers,
        answerable=bool(answers),
    )
