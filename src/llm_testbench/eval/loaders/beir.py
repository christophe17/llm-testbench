"""BEIR (SciFact, NFCorpus, FiQA) : corpus + requêtes + jugements de pertinence.

Piège : les qrels vivent dans des repos Hugging Face **séparés**
(``BeIR/{name}-qrels``). Les oublier donne un corpus interrogeable mais
inévaluable. Autre piège : la majorité des requêtes des fichiers ``queries``
n'ont aucun jugement — on ne garde que les requêtes jugées.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from datasets import load_dataset

from llm_testbench.config import get_settings
from llm_testbench.eval.types import Document, Query, RetrievalDataset

BEIR_DATASETS = ("scifact", "nfcorpus", "fiqa")

Row = Mapping[str, Any]


def parse_corpus(rows: Iterable[Row]) -> list[Document]:
    return [
        Document(doc_id=str(r["_id"]), title=r.get("title") or "", text=r["text"]) for r in rows
    ]


def parse_queries(rows: Iterable[Row]) -> list[Query]:
    return [Query(query_id=str(r["_id"]), text=r["text"]) for r in rows]


def parse_qrels(rows: Iterable[Row]) -> dict[str, dict[str, int]]:
    qrels: dict[str, dict[str, int]] = {}
    for r in rows:
        qrels.setdefault(str(r["query-id"]), {})[str(r["corpus-id"])] = int(r["score"])
    return qrels


def build_retrieval_dataset(
    name: str,
    corpus_rows: Iterable[Row],
    query_rows: Iterable[Row],
    qrels_rows: Iterable[Row],
) -> RetrievalDataset:
    """Assemblage pur (testable hors ligne) : filtre les requêtes non jugées."""
    qrels = parse_qrels(qrels_rows)
    queries = [q for q in parse_queries(query_rows) if q.query_id in qrels]
    return RetrievalDataset(
        name=f"beir/{name}",
        documents=parse_corpus(corpus_rows),
        queries=queries,
        qrels=qrels,
    )


def load_beir(name: str, qrels_split: str = "test") -> RetrievalDataset:
    if name not in BEIR_DATASETS:
        raise ValueError(
            f"Jeu BEIR non retenu au banc d'essai : {name!r} (choix : {BEIR_DATASETS})"
        )
    cache = str(get_settings().hf_cache_dir)
    corpus = load_dataset(f"BeIR/{name}", "corpus", split="corpus", cache_dir=cache)
    queries = load_dataset(f"BeIR/{name}", "queries", split="queries", cache_dir=cache)
    qrels = load_dataset(f"BeIR/{name}-qrels", split=qrels_split, cache_dir=cache)
    return build_retrieval_dataset(name, corpus, queries, qrels)
