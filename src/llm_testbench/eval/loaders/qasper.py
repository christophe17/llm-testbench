"""Loader QASPER — des articles scientifiques complets, en sections (Dasigi et al. 2021).

Pourquoi lui en phase 1 : c'est le jeu que le brief désigne pour le chunking « sur
documents bruts » (phase 3), et son texte intégral est déjà structuré en sections et
paragraphes dans le Parquet — des documents longs sans parser de PDF. Les questions et
réponses annotées du jeu servent en phase 2 ; ici on ne charge que ce qu'il faut pour
produire des :class:`ParsedDocument`.

Particularités de la distribution (vérifiées le 2026-09-03) : dépôt ``allenai/qasper`` à
script, converti en Parquet par Hugging Face sur la branche ``refs/convert/parquet``
(la seule chargeable avec ``datasets`` ≥ 3) ; splits train 888 / validation 281 /
test 416 ; ``full_text`` est un dictionnaire de listes parallèles (``section_name``,
``paragraphs``) ; licence CC BY 4.0 (étiquette HF).
"""

import json
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm_testbench.config import Settings, get_settings
from llm_testbench.eval.types import DatasetInfo
from llm_testbench.ingest.parsing import ParsedDocument, parse_sections

QASPER_INFO = DatasetInfo(
    key="qasper",
    name="QASPER",
    homepage="https://allenai.org/data/qasper",
    license="cc-by-4.0 (étiquette du dépôt HF)",
    source="hf:allenai/qasper (branche refs/convert/parquet)",
)

Row = dict[str, Any]


class QasperQuestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    question_id: str
    question: str


class QasperPaper(BaseModel):
    model_config = ConfigDict(frozen=True)

    paper_id: str
    title: str
    abstract: str
    sections: tuple[tuple[str, str], ...]
    """(nom de section, paragraphes joints par une ligne vide), sections vides écartées."""
    questions: tuple[QasperQuestion, ...] = ()
    split: str

    def to_document(self) -> ParsedDocument:
        return parse_sections(
            self.paper_id,
            [("Abstract", self.abstract), *self.sections],
            title=self.title,
            source_uri=f"hf:allenai/qasper/{self.split}/{self.paper_id}",
            metadata={"dataset": "qasper", "split": self.split},
        )


class QasperDataset(BaseModel):
    model_config = ConfigDict(frozen=True)

    info: DatasetInfo
    split: str
    papers: tuple[QasperPaper, ...] = Field(min_length=1)
    sampled: bool = False

    def documents(self) -> list[ParsedDocument]:
        return [paper.to_document() for paper in self.papers]

    def describe(self) -> dict[str, int | str | bool]:
        return {
            "dataset": self.info.key,
            "split": self.split,
            "papers": len(self.papers),
            "sections": sum(len(p.sections) for p in self.papers),
            "questions": sum(len(p.questions) for p in self.papers),
            "sampled": self.sampled,
        }


def _sections(full_text: Any) -> tuple[tuple[str, str], ...]:
    """``full_text`` arrive soit en dictionnaire de listes parallèles (HF), soit en liste
    de dictionnaires (fixtures écrites à la main) : on accepte les deux."""
    pairs: Iterable[tuple[Any, Any]]
    if isinstance(full_text, dict):
        names = full_text.get("section_name") or []
        paragraphs = full_text.get("paragraphs") or []
        pairs = zip(names, paragraphs, strict=True)
    else:
        pairs = ((s.get("section_name"), s.get("paragraphs")) for s in full_text or [])
    sections: list[tuple[str, str]] = []
    for name, paras in pairs:
        text = "\n\n".join(p.strip() for p in (paras or []) if p and p.strip())
        if text:
            sections.append(((name or "").strip(), text))
    return tuple(sections)


def _questions(qas: Any) -> tuple[QasperQuestion, ...]:
    if isinstance(qas, dict):
        ids = qas.get("question_id") or []
        texts = qas.get("question") or []
        return tuple(
            QasperQuestion(question_id=str(i), question=str(q))
            for i, q in zip(ids, texts, strict=True)
        )
    return tuple(
        QasperQuestion(question_id=str(q["question_id"]), question=str(q["question"]))
        for q in qas or []
    )


def paper_from_row(row: Row, split: str) -> QasperPaper:
    return QasperPaper(
        paper_id=str(row["id"]),
        title=str(row.get("title") or ""),
        abstract=str(row.get("abstract") or ""),
        sections=_sections(row.get("full_text")),
        questions=_questions(row.get("qas")),
        split=split,
    )


class QasperLoader:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings if settings is not None else get_settings()

    @property
    def info(self) -> DatasetInfo:
        return QASPER_INFO

    def load(self, split: str = "validation", max_papers: int | None = None) -> QasperDataset:
        rows = self._load_rows(split)
        sampled = max_papers is not None and len(rows) > max_papers
        if sampled:
            rows = rows[:max_papers]
        papers = tuple(paper_from_row(row, split) for row in rows)
        return QasperDataset(info=self.info, split=split, papers=papers, sampled=sampled)

    def _load_rows(self, split: str) -> list[Row]:
        fixtures_dir = self._settings.fixtures_dir
        if fixtures_dir is not None:
            path = fixtures_dir / "qasper" / f"{split}.json"
            if not path.is_file():
                raise FileNotFoundError(f"fixture absente : {path}")
            rows: list[Row] = json.loads(path.read_text(encoding="utf-8"))
            return rows
        return self._load_rows_from_hf(split)

    def _load_rows_from_hf(self, split: str) -> list[Row]:
        from datasets import load_dataset

        dataset = load_dataset(
            "allenai/qasper",
            split=split,
            revision="refs/convert/parquet",
            cache_dir=str(self._settings.data_dir / "hf"),
        )
        return list(dataset)
