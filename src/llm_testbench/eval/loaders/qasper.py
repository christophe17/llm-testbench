"""QASPER loader — complete scientific papers, in sections (Dasigi et al. 2021).

Why this one in phase 1: it is the dataset the brief designates for chunking "on raw
documents" (phase 3), and its full text is already structured in sections and
paragraphs in the Parquet — long documents without a PDF parser.

Phase 2 reads the annotations too (:meth:`QasperLoader.load_qa`). A question is asked about
one paper by someone who read only its title and abstract; one to three annotators then
read the paper and each gives an answer of one of four kinds (spans copied from the paper,
a free-form sentence, yes or no, or "unanswerable") with the paragraphs that support it.
Three things to know before trusting a number on it:

- annotators disagree: a question is kept only when they agree on whether it can be
  answered at all;
- some evidence is a table or a figure (``FLOAT SELECTED: ...``, 9% of the evidence of the
  validation split): the text of the paper does not contain it, so a question supported
  only by floats is left out of a text-only measurement;
- the search is **scoped to the paper**, as the dataset defines the task: "which baselines
  do they compare with?" means nothing across 281 papers.

Specifics of the distribution (verified on 2026-09-03): script-based repository
``allenai/qasper``, converted to Parquet by Hugging Face on the ``refs/convert/parquet``
branch (the only one loadable with ``datasets`` ≥ 3); splits train 888 / validation 281 /
test 416; ``full_text`` is a dictionary of parallel lists (``section_name``,
``paragraphs``); license CC BY 4.0 (HF label).
"""

import json
from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from llm_testbench.config import Settings, get_settings
from llm_testbench.eval.qa import Passage, QADataset, QAExample, balanced_subsample
from llm_testbench.eval.types import DatasetInfo
from llm_testbench.ingest.parsing import ParsedDocument, parse_sections

QASPER_INFO = DatasetInfo(
    key="qasper",
    name="QASPER",
    homepage="https://allenai.org/data/qasper",
    license="cc-by-4.0 (label of the HF repository)",
    source="hf:allenai/qasper (branch refs/convert/parquet)",
)

Row = dict[str, Any]


FLOAT_EVIDENCE = "FLOAT SELECTED"
"""Prefix of an evidence entry that points at a table or a figure, not at a paragraph."""

AnswerKind = Literal["extractive", "abstractive", "yes_no", "unanswerable"]


class QasperAnswer(BaseModel):
    """One annotator's answer to a question."""

    model_config = ConfigDict(frozen=True)

    kind: AnswerKind
    text: str = ""
    """The answer as QASPER scores it: the spans joined by a comma, the free-form
    sentence, ``Yes`` or ``No``; empty when unanswerable."""
    evidence: tuple[str, ...] = ()
    """The paragraphs of the paper the annotator selected; tables and figures left out."""
    float_evidence: bool = False
    """The annotator also (or only) pointed at a table or a figure."""


class QasperQuestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    question_id: str
    question: str
    answers: tuple[QasperAnswer, ...] = ()


class QasperPaper(BaseModel):
    model_config = ConfigDict(frozen=True)

    paper_id: str
    title: str
    abstract: str
    sections: tuple[tuple[str, str], ...]
    """(section name, paragraphs joined by a blank line), empty sections dropped."""
    questions: tuple[QasperQuestion, ...] = ()
    split: str

    def to_document(self) -> ParsedDocument:
        return parse_sections(
            self.paper_id,
            [("Abstract", self.abstract), *self.sections],
            title=self.title,
            source_uri=f"hf:allenai/qasper/{self.split}/{self.paper_id}",
            # paper_id: what a question's scope filters on (retrieval inside one paper).
            metadata={"dataset": "qasper", "split": self.split, "paper_id": self.paper_id},
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
    """``full_text`` arrives either as a dictionary of parallel lists (HF) or as a list of
    dictionaries (hand-written fixtures): we accept both."""
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


def _answer(raw: dict[str, Any]) -> QasperAnswer:
    entries = [str(entry).strip() for entry in raw.get("evidence") or []]
    evidence = tuple(e for e in entries if e and not e.startswith(FLOAT_EVIDENCE))
    floats = any(e.startswith(FLOAT_EVIDENCE) for e in entries)
    spans = [str(span).strip() for span in raw.get("extractive_spans") or [] if str(span).strip()]
    free_form = str(raw.get("free_form_answer") or "").strip()
    kind: AnswerKind
    if raw.get("unanswerable"):
        kind, text = "unanswerable", ""
    elif spans:
        kind, text = "extractive", ", ".join(spans)
    elif free_form:
        kind, text = "abstractive", free_form
    elif raw.get("yes_no") is not None:
        kind, text = "yes_no", "Yes" if raw["yes_no"] else "No"
    else:
        kind, text = "unanswerable", ""
    return QasperAnswer(kind=kind, text=text, evidence=evidence, float_evidence=floats)


def _answers(raw: Any) -> tuple[QasperAnswer, ...]:
    """The annotations of one question: ``{"answer": [...]}`` on Hugging Face, a plain
    list in the hand-written fixtures, nothing at all in the phase 1 fixtures."""
    if raw is None:
        return ()
    entries = raw.get("answer") or [] if isinstance(raw, dict) else raw
    return tuple(_answer(entry) for entry in entries)


def _questions(qas: Any) -> tuple[QasperQuestion, ...]:
    if isinstance(qas, dict):
        ids = qas.get("question_id") or []
        texts = qas.get("question") or []
        answers = qas.get("answers") or [None] * len(ids)
        return tuple(
            QasperQuestion(question_id=str(i), question=str(q), answers=_answers(a))
            for i, q, a in zip(ids, texts, answers, strict=True)
        )
    return tuple(
        QasperQuestion(
            question_id=str(q["question_id"]),
            question=str(q["question"]),
            answers=_answers(q.get("answers")),
        )
        for q in qas or []
    )


def qa_example(paper: QasperPaper, question: QasperQuestion) -> QAExample | None:
    """The question as the generation runner takes it, or ``None`` when it cannot be
    scored from the text: no annotation, annotators who disagree on whether an answer
    exists, or an answer supported by tables and figures only."""
    if not question.answers:
        return None
    unanswerable = [answer.kind == "unanswerable" for answer in question.answers]
    scope = {"paper_id": paper.paper_id}
    if all(unanswerable):
        return QAExample(
            example_id=question.question_id,
            question=question.question,
            answerable=False,
            scope=scope,
            kind="unanswerable",
        )
    if any(unanswerable):
        return None
    paragraphs = list(
        dict.fromkeys(text for answer in question.answers for text in answer.evidence)
    )
    if not paragraphs:
        return None
    return QAExample(
        example_id=question.question_id,
        question=question.question,
        passages=tuple(
            Passage(
                passage_id=f"{question.question_id}#evidence-{number}",
                title=paper.title,
                text=text,
                document_id=paper.paper_id,
            )
            for number, text in enumerate(paragraphs, start=1)
        ),
        answers=tuple(dict.fromkeys(answer.text for answer in question.answers if answer.text)),
        answerable=True,
        scope=scope,
        kind=question.answers[0].kind,
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

    def load_qa(
        self, split: str = "validation", *, max_examples: int | None = None, seed: int = 0
    ) -> QADataset:
        """The questions that can be scored from the text, with the whole split as the
        corpus: a question is searched inside its paper, but the index holds them all, as
        a real one would."""
        max_papers = self._settings.sample_max_queries if self._settings.sample else None
        papers = self.load(split, max_papers=max_papers).papers
        examples = [
            example
            for paper in papers
            for question in paper.questions
            if (example := qa_example(paper, question)) is not None
        ]
        subsample_seed: int | None = None
        if max_examples is not None and len(examples) > max_examples:
            examples = balanced_subsample(examples, max_examples, seed)
            subsample_seed = seed
        return QADataset(
            info=self.info,
            split=split,
            examples=tuple(examples),
            subsample_seed=subsample_seed,
            corpus=tuple(paper.to_document() for paper in papers),
        )

    def _load_rows(self, split: str) -> list[Row]:
        fixtures_dir = self._settings.fixtures_dir
        if fixtures_dir is not None:
            path = fixtures_dir / "qasper" / f"{split}.json"
            if not path.is_file():
                raise FileNotFoundError(f"missing fixture: {path}")
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
