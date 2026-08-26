"""SQuAD 2.0 : le jeu de l'abstention.

~la moitié des questions de la validation sont **non répondables** (écrites
adversarialement pour ressembler à des répondables). Le marqueur est implicite :
une liste ``answers.text`` vide. Le harness s'en servira pour mesurer le taux de
refus correct et le taux de refus abusif — séparément de l'exactitude.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from datasets import load_dataset

from llm_testbench.config import get_settings
from llm_testbench.eval.types import Document, QADataset, QAExample

Row = Mapping[str, Any]


def parse_squad_row(row: Row) -> QAExample:
    # Les réponses répétées par plusieurs annotateurs sont dédoublonnées, ordre préservé.
    answers = list(dict.fromkeys(row["answers"]["text"]))
    return QAExample(
        example_id=str(row["id"]),
        question=row["question"],
        contexts=[
            Document(doc_id=str(row["id"]), title=row.get("title") or "", text=row["context"])
        ],
        answers=answers,
        is_answerable=bool(answers),
        metadata={"title": row.get("title") or ""},
    )


def build_qa_dataset(split: str, rows: Iterable[Row]) -> QADataset:
    return QADataset(name="squad_v2", split=split, examples=[parse_squad_row(r) for r in rows])


def load_squad_v2(split: str = "validation") -> QADataset:
    rows = load_dataset(
        "rajpurkar/squad_v2", split=split, cache_dir=str(get_settings().hf_cache_dir)
    )
    return build_qa_dataset(split, rows)
