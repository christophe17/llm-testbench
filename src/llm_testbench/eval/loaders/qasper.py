"""QASPER : articles scientifiques **entiers** + questions ancrées sur des preuves.

C'est le seul jeu du starter qui fournit des documents bruts non pré-découpés —
le support du duel de stratégies de chunking (phase 3). Chaque question a
plusieurs annotations ; convention retenue ici : un exemple est non répondable
si **toutes** ses annotations le marquent ``unanswerable`` (les annotations
divergentes restantes fournissent les réponses et les preuves).
"""

from collections.abc import Iterable, Mapping
from typing import Any

from datasets import load_dataset

from llm_testbench.config import get_settings
from llm_testbench.eval.types import PaperSection, QAExample, QasperPaper

Row = Mapping[str, Any]


def _collect_answers(annotations: list[Mapping[str, Any]]) -> tuple[list[str], list[str], bool]:
    """Retourne (réponses, preuves, is_answerable) agrégées sur les annotations."""
    answers: list[str] = []
    evidence: list[str] = []
    unanswerable_votes = 0
    for ann in annotations:
        if ann["unanswerable"]:
            unanswerable_votes += 1
            continue
        if ann["free_form_answer"]:
            answers.append(ann["free_form_answer"])
        answers.extend(ann["extractive_spans"])
        if ann["yes_no"] is not None:
            answers.append("yes" if ann["yes_no"] else "no")
        evidence.extend(ann["highlighted_evidence"])
    is_answerable = len(annotations) > 0 and unanswerable_votes < len(annotations)
    return list(dict.fromkeys(answers)), list(dict.fromkeys(evidence)), is_answerable


def parse_qasper_row(row: Row) -> QasperPaper:
    full_text = row["full_text"]
    sections = [
        PaperSection(section_name=name or "", paragraphs=list(paragraphs))
        for name, paragraphs in zip(full_text["section_name"], full_text["paragraphs"], strict=True)
    ]
    questions: list[QAExample] = []
    qas = row["qas"]
    for i, (question_id, question) in enumerate(
        zip(qas["question_id"], qas["question"], strict=True)
    ):
        answers, evidence, is_answerable = _collect_answers(qas["answers"][i]["answer"])
        questions.append(
            QAExample(
                example_id=str(question_id),
                question=question,
                answers=answers,
                is_answerable=is_answerable,
                evidence=evidence,
            )
        )
    return QasperPaper(
        paper_id=str(row["id"]),
        title=row["title"],
        abstract=row["abstract"],
        sections=sections,
        questions=questions,
    )


def build_papers(rows: Iterable[Row]) -> list[QasperPaper]:
    return [parse_qasper_row(r) for r in rows]


def load_qasper(split: str = "validation") -> list[QasperPaper]:
    # allenai/qasper héberge encore un script de chargement, refusé par datasets>=3.0 ;
    # la branche refs/convert/parquet expose les mêmes données sans script.
    rows = load_dataset(
        "allenai/qasper",
        revision="refs/convert/parquet",
        split=split,
        cache_dir=str(get_settings().hf_cache_dir),
    )
    return build_papers(rows)
