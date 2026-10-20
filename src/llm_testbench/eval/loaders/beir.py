"""BEIR loader — reference dataset of phase 0: SciFact.

Specifics of the BEIR distribution on Hugging Face (verified on 2026-08-26):

- each dataset lives in TWO repositories: ``BeIR/<dataset>`` (configs ``corpus`` and
  ``queries``) and ``BeIR/<dataset>-qrels`` (splits ``train``/``test``). The loader
  therefore joins three tables;
- the repositories are native Parquet — loading without a script, compatible with
  ``datasets`` >= 3;
- the queries file contains MORE queries than the split judges (SciFact: 1,109
  queries, 300 judged in test). Queries without qrels in the requested split are
  dropped — otherwise any recall computation would be skewed.

Sample mode: we keep the first ``max_queries`` judged queries (file order, hence
deterministic) and only the documents they judge. The corpus then has no
distractors left: the mechanics can be checked, a retrieval score would mean
nothing there — hence the ``sampled=True`` marking.
"""

import json
from pathlib import Path
from typing import Any

from llm_testbench.config import Settings, get_settings
from llm_testbench.eval.loaders.base import RetrievalLoader
from llm_testbench.eval.types import DatasetInfo, Document, Qrels, Query, RetrievalDataset

# Only dataset wired in phase 0. Adding one = an entry here + its fixtures + its tests.
BEIR_DATASETS: dict[str, DatasetInfo] = {
    "scifact": DatasetInfo(
        key="beir/scifact",
        name="SciFact (BEIR)",
        homepage="https://github.com/allenai/scifact",
        license="cc-by-sa-4.0 (claim of the BEIR packaging, see ADR 001)",
        source="hf:BeIR/scifact + hf:BeIR/scifact-qrels",
    ),
}

Row = dict[str, Any]


class BeirLoader(RetrievalLoader):
    def __init__(self, dataset: str = "scifact", settings: Settings | None = None) -> None:
        if dataset not in BEIR_DATASETS:
            raise ValueError(
                f"BEIR dataset not wired: {dataset!r} (known: {sorted(BEIR_DATASETS)})"
            )
        self._dataset = dataset
        self._settings = settings if settings is not None else get_settings()

    @property
    def info(self) -> DatasetInfo:
        return BEIR_DATASETS[self._dataset]

    def load(self, split: str = "test", max_queries: int | None = None) -> RetrievalDataset:
        corpus_rows, query_rows, qrels_rows = self._load_rows(split)
        return build_retrieval_dataset(
            info=self.info,
            split=split,
            corpus_rows=corpus_rows,
            query_rows=query_rows,
            qrels_rows=qrels_rows,
            max_queries=max_queries,
        )

    # ------------------------------------------------------------------ sources

    def _load_rows(self, split: str) -> tuple[list[Row], list[Row], list[Row]]:
        fixtures_dir = self._settings.fixtures_dir
        if fixtures_dir is not None:
            return self._load_rows_from_fixtures(fixtures_dir, split)
        return self._load_rows_from_hf(split)

    def _load_rows_from_hf(self, split: str) -> tuple[list[Row], list[Row], list[Row]]:
        from datasets import load_dataset

        cache_dir = str(self._settings.data_dir / "hf")
        repo = f"BeIR/{self._dataset}"
        corpus = load_dataset(repo, "corpus", split="corpus", cache_dir=cache_dir)
        queries = load_dataset(repo, "queries", split="queries", cache_dir=cache_dir)
        qrels = load_dataset(f"{repo}-qrels", split=split, cache_dir=cache_dir)
        return list(corpus), list(queries), list(qrels)

    def _load_rows_from_fixtures(
        self, fixtures_dir: Path, split: str
    ) -> tuple[list[Row], list[Row], list[Row]]:
        base = fixtures_dir / "beir" / self._dataset
        return (
            _read_json_rows(base / "corpus.json"),
            _read_json_rows(base / "queries.json"),
            _read_json_rows(base / f"qrels_{split}.json"),
        )


def _read_json_rows(path: Path) -> list[Row]:
    if not path.is_file():
        raise FileNotFoundError(f"missing fixture: {path}")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"invalid fixture (list expected): {path}")
    return rows


# -------------------------------------------------------------------------- join


def build_retrieval_dataset(
    info: DatasetInfo,
    split: str,
    corpus_rows: list[Row],
    query_rows: list[Row],
    qrels_rows: list[Row],
    max_queries: int | None = None,
) -> RetrievalDataset:
    """Join corpus + queries + qrels into a validated dataset.

    Pure and independent of the source of the rows: it is what the offline tests
    cover, the same function that runs on the real data.
    """
    qrels: Qrels = {}
    for row in qrels_rows:
        # The qrels ids sometimes arrive typed as int on the HF side: everything becomes str.
        query_id, doc_id = str(row["query-id"]), str(row["corpus-id"])
        qrels.setdefault(query_id, {})[doc_id] = int(row["score"])

    judged_queries = [
        Query(query_id=str(row["_id"]), text=row["text"])
        for row in query_rows
        if str(row["_id"]) in qrels
    ]

    sampled = max_queries is not None and len(judged_queries) > max_queries
    if sampled:
        judged_queries = judged_queries[:max_queries]
        kept_ids = {q.query_id for q in judged_queries}
        qrels = {qid: judged for qid, judged in qrels.items() if qid in kept_ids}
        judged_doc_ids = {doc_id for judged in qrels.values() for doc_id in judged}
        corpus_rows = [row for row in corpus_rows if str(row["_id"]) in judged_doc_ids]

    documents = tuple(
        Document(doc_id=str(row["_id"]), title=row.get("title", ""), text=row["text"])
        for row in corpus_rows
    )
    return RetrievalDataset(
        info=info,
        split=split,
        documents=documents,
        queries=tuple(judged_queries),
        qrels=qrels,
        sampled=sampled,
    )
