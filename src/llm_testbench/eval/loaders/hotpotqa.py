"""HotpotQA (config ``distractor``) : multi-hop avec preuves annotées.

Chaque question vient avec 10 paragraphes dont 2 en or (``supporting_facts``) et
8 distracteurs : le retrieval est donc évaluable au niveau du paragraphe. Le
split ``test`` du fullwiki n'a pas de labels (leaderboard) — on travaille sur la
validation. Faiblesse connue : une partie des questions est répondable en un
seul hop ; MuSiQue est le complément dur (ajouté plus tard si besoin).
"""

from collections.abc import Iterable, Mapping
from typing import Any

from datasets import load_dataset

from llm_testbench.config import get_settings
from llm_testbench.eval.types import Document, QADataset, QAExample

Row = Mapping[str, Any]


def parse_hotpot_row(row: Row) -> QAExample:
    titles: list[str] = row["context"]["title"]
    sentences: list[list[str]] = row["context"]["sentences"]
    contexts = [
        Document(doc_id=title, title=title, text="".join(sents))
        for title, sents in zip(titles, sentences, strict=True)
    ]
    supporting = list(dict.fromkeys(row["supporting_facts"]["title"]))
    return QAExample(
        example_id=str(row["id"]),
        question=row["question"],
        contexts=contexts,
        answers=[row["answer"]],
        is_answerable=True,
        supporting_doc_ids=supporting,
        metadata={"level": row["level"], "type": row["type"]},
    )


def build_qa_dataset(split: str, rows: Iterable[Row]) -> QADataset:
    return QADataset(name="hotpotqa", split=split, examples=[parse_hotpot_row(r) for r in rows])


def load_hotpotqa(split: str = "validation") -> QADataset:
    rows = load_dataset(
        "hotpotqa/hotpot_qa",
        "distractor",
        split=split,
        cache_dir=str(get_settings().hf_cache_dir),
    )
    return build_qa_dataset(split, rows)
