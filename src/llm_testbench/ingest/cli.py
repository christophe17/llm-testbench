"""Ingestion en ligne de commande : ``python -m llm_testbench.ingest.cli scifact``.

Charge un jeu public, le convertit en documents, et l'indexe dans la base configurée.
Requiert la clé du provider d'embeddings (``OPENAI_API_KEY`` pour le modèle par défaut).
"""

import argparse
import asyncio
import sys

from llm_testbench.config import Settings, get_settings
from llm_testbench.eval.loaders import BeirLoader, QasperLoader
from llm_testbench.ingest.chunking import RecursiveChunker
from llm_testbench.ingest.parsing import ParsedDocument, parse_sections
from llm_testbench.ingest.pipeline import IngestionPipeline, IngestReport
from llm_testbench.ingest.store import PgVectorStore
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.governance import DataClass

DEFAULT_EMBEDDING_DIMENSIONS = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}


def scifact_documents(settings: Settings, max_docs: int | None) -> list[ParsedDocument]:
    dataset = BeirLoader("scifact", settings).load("test")
    documents = [
        parse_sections(
            doc.doc_id,
            [("", doc.text)],
            title=doc.title,
            source_uri=f"hf:BeIR/scifact/{doc.doc_id}",
            metadata={"dataset": "scifact"},
        )
        for doc in dataset.documents
    ]
    return documents[:max_docs] if max_docs is not None else documents


def qasper_documents(settings: Settings, max_docs: int | None) -> list[ParsedDocument]:
    return QasperLoader(settings).load("validation", max_papers=max_docs).documents()


async def run(
    *,
    dataset: str,
    index_key: str,
    embedding_model: str,
    dimensions: int | None,
    chunk_size: int,
    chunk_overlap: int,
    max_docs: int | None,
) -> IngestReport:
    settings = get_settings()
    if settings.database_url is None:
        raise SystemExit("LLM_TESTBENCH_DATABASE_URL est requis")
    model_name = embedding_model.rpartition("/")[2]
    dims = dimensions or DEFAULT_EMBEDDING_DIMENSIONS.get(model_name)
    if dims is None:
        raise SystemExit(f"dimension inconnue pour {embedding_model!r} : passer --dimensions")
    documents = (
        scifact_documents(settings, max_docs)
        if dataset == "scifact"
        else qasper_documents(settings, max_docs)
    )
    client = LLMClient.from_settings(settings)
    async with PgVectorStore.from_url(settings.database_url) as store:
        pipeline = IngestionPipeline(
            client=client,
            store=store,
            chunker=RecursiveChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap),
            data_class=DataClass.PUBLIC,
        )
        spec = pipeline.index_spec(
            index_key=index_key,
            source_key=f"docs:{dataset}",
            embedding_model=embedding_model,
            dimensions=dims,
            description=f"{dataset} / recursive({chunk_size}/{chunk_overlap}) / {embedding_model}",
        )
        return await pipeline.ingest(spec, documents)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Indexe un jeu public dans pgvector.")
    parser.add_argument("dataset", choices=["scifact", "qasper"])
    parser.add_argument("--index-key", default=None)
    parser.add_argument("--embedding-model", default="openai/text-embedding-3-small")
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--chunk-size", type=int, default=1_000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--max-docs", type=int, default=None, help="tronque (test rapide)")
    args = parser.parse_args(argv)
    index_key = args.index_key or f"{args.dataset}-recursive-oai-small"
    report = asyncio.run(
        run(
            dataset=args.dataset,
            index_key=index_key,
            embedding_model=args.embedding_model,
            dimensions=args.dimensions,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            max_docs=args.max_docs,
        )
    )
    sys.stdout.write(report.model_dump_json(indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
