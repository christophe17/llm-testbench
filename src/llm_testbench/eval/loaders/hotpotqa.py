"""HotpotQA loader: questions that need two Wikipedia paragraphs at once (Yang et al. 2018).

A *multi-hop* question cannot be answered from one passage: "Were Scott Derrickson and Ed
Wood of the same nationality?" needs the paragraph of each. It is the dataset where
retrieval fails in an instructive way: finding one of the two paragraphs is not enough.

Verified on 2026-11-05: ``hotpotqa/hotpot_qa`` on Hugging Face, native Parquet,
CC BY-SA 4.0, revision pinned below. Two settings exist. *Full wiki* searches 5.2 million
paragraphs, which does not fit a local pgvector. *Distractor* gives each question ten
paragraphs: its two gold ones and eight look-alikes picked by a TF-IDF retriever. The test
answers are hidden, so ``validation`` (7,405 questions, all rated "hard") is the evaluation
set.

What this loader builds from the distractor setting: a **pool**. ``pool`` questions are
drawn with a fixed seed, and the paragraphs of all of them, deduplicated by title, become
one corpus (1,000 questions: 9,789 paragraphs). Each question then has its two gold
paragraphs, its own eight distractors, and the paragraphs of 999 other questions to get
lost in. Two views of the same pool:

- :meth:`HotpotQALoader.load_retrieval`: corpus, queries, judgments, for the retrieval
  harness (which paragraphs come back);
- :meth:`HotpotQALoader.load`: questions, gold paragraphs and reference answers, for the
  generation runner, with the corpus attached for the end-to-end run.

No published score applies to such a pool: the BEIR numbers for HotpotQA are measured on
the full 5.2 million paragraphs, and the distractor leaderboard ranks readers that receive
the ten paragraphs, not a retriever. The numbers measured here are compared with each
other (gold context against retrieved context), not with the literature.
"""

import json
import random
from typing import Any

from llm_testbench.config import Settings, get_settings
from llm_testbench.eval.qa import Passage, QADataset, QAExample
from llm_testbench.eval.types import DatasetInfo, Document, Qrels, Query, RetrievalDataset
from llm_testbench.ingest.parsing import parse_sections

HOTPOTQA_REVISION = "1908d6afbbead072334abe2965f91bd2709910ab"
POOL_SEED = 0
"""The pool is one fixed draw: the corpus of an index must not depend on a run's seed."""

Row = dict[str, Any]


def hotpotqa_info(pool: int) -> DatasetInfo:
    return DatasetInfo(
        key=f"hotpotqa/pool-{pool}",
        name=f"HotpotQA (distractor setting, pool of {pool} questions)",
        homepage="https://hotpotqa.github.io/",
        license="cc-by-sa-4.0 (label of the HF repository)",
        source=f"hf:hotpotqa/hotpot_qa (distractor, revision {HOTPOTQA_REVISION[:7]})",
    )


def _paragraphs(row: Row) -> dict[str, str]:
    """title -> text of the ten paragraphs of a question. The sentences carry their own
    leading spaces: joined as they are, they give the paragraph back."""
    context = row["context"]
    paragraphs: dict[str, str] = {}
    for title, sentences in zip(context["title"], context["sentences"], strict=True):
        text = "".join(sentences).strip()
        if text:
            paragraphs[str(title)] = text
    return paragraphs


def _gold_titles(row: Row) -> list[str]:
    return list(dict.fromkeys(str(title) for title in row["supporting_facts"]["title"]))


class HotpotQALoader:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings if settings is not None else get_settings()

    def load_retrieval(self, split: str = "validation", *, pool: int = 1_000) -> RetrievalDataset:
        rows = self._pool(split, pool)
        documents: dict[str, Document] = {}
        queries: list[Query] = []
        qrels: Qrels = {}
        for row in rows:
            for title, text in _paragraphs(row).items():
                documents.setdefault(title, Document(doc_id=title, title=title, text=text))
            queries.append(Query(query_id=str(row["id"]), text=row["question"].strip()))
            qrels[str(row["id"])] = dict.fromkeys(_gold_titles(row), 1)
        return RetrievalDataset(
            info=hotpotqa_info(pool),
            split=split,
            documents=tuple(documents.values()),
            queries=tuple(queries),
            qrels=qrels,
            sampled=self._settings.sample,
        )

    def load(
        self,
        split: str = "validation",
        *,
        pool: int = 1_000,
        max_examples: int | None = None,
        seed: int = 0,
    ) -> QADataset:
        rows = self._pool(split, pool)
        corpus: dict[str, str] = {}
        for row in rows:
            for title, text in _paragraphs(row).items():
                corpus.setdefault(title, text)
        info = hotpotqa_info(pool)
        location = info.source.split(" ")[0]
        examples = [_example(row) for row in rows]
        subsample_seed: int | None = None
        if max_examples is not None and len(examples) > max_examples:
            kept = {
                example.example_id for example in random.Random(seed).sample(examples, max_examples)
            }
            examples = [example for example in examples if example.example_id in kept]
            subsample_seed = seed
        return QADataset(
            info=info,
            split=split,
            examples=tuple(examples),
            subsample_seed=subsample_seed,
            corpus=tuple(
                parse_sections(
                    title,
                    [("", text)],
                    title=title,
                    source_uri=f"{location}/{title}",
                    metadata={"dataset": "hotpotqa"},
                )
                for title, text in corpus.items()
            ),
        )

    def _pool(self, split: str, pool: int) -> list[Row]:
        """``pool`` questions drawn with the fixed seed, in the order of the file. A
        question whose gold paragraph is missing from its own context is left out."""
        rows = [row for row in self._rows(split) if set(_gold_titles(row)) <= set(_paragraphs(row))]
        if self._settings.sample:
            pool = min(pool, self._settings.sample_max_queries)
        if len(rows) <= pool:
            return rows
        kept = set(random.Random(POOL_SEED).sample(range(len(rows)), pool))
        return [row for index, row in enumerate(rows) if index in kept]

    def _rows(self, split: str) -> list[Row]:
        fixtures_dir = self._settings.fixtures_dir
        if fixtures_dir is not None:
            path = fixtures_dir / "hotpotqa" / f"{split}.json"
            if not path.is_file():
                raise FileNotFoundError(f"missing fixture: {path}")
            rows: list[Row] = json.loads(path.read_text(encoding="utf-8"))
            return rows
        from datasets import load_dataset

        # data_files: only this split's file is downloaded (27 MB), not the 330 MB of train.
        return list(
            load_dataset(
                "hotpotqa/hotpot_qa",
                data_files={split: f"distractor/{split}-*.parquet"},
                split=split,
                revision=HOTPOTQA_REVISION,
                cache_dir=str(self._settings.data_dir / "hf"),
            )
        )


def _example(row: Row) -> QAExample:
    paragraphs = _paragraphs(row)
    return QAExample(
        example_id=str(row["id"]),
        question=row["question"].strip(),
        passages=tuple(
            Passage(passage_id=title, title=title, text=paragraphs[title], document_id=title)
            for title in _gold_titles(row)
        ),
        answers=(str(row["answer"]).strip(),),
        answerable=True,
        kind=str(row.get("type") or ""),
    )
