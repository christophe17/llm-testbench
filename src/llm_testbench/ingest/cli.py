"""Command-line ingestion: ``python -m llm_testbench.ingest.cli scifact``.

Loads a public dataset, converts it into documents, and indexes it in the configured
database. Requires the embedding provider key (``OPENAI_API_KEY`` for the default model) and
``LLM_TESTBENCH_DATABASE_URL``, from the environment or from ``.env`` at the repository root.
"""

import argparse
import asyncio
import sys

from llm_testbench.config import Settings, get_settings, load_env_file
from llm_testbench.eval.loaders import BeirLoader, QasperLoader
from llm_testbench.eval.loaders.beir import BEIR_DATASETS
from llm_testbench.ingest.chunking import NO_SPLIT, RecursiveChunker
from llm_testbench.ingest.parsing import ParsedDocument
from llm_testbench.ingest.pipeline import IngestionPipeline, IngestReport
from llm_testbench.ingest.store import PgVectorStore
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.governance import DataClass


def beir_documents(settings: Settings, dataset: str, max_docs: int | None) -> list[ParsedDocument]:
    documents = BeirLoader(dataset, settings).load("test").parsed_documents()
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
        raise SystemExit("LLM_TESTBENCH_DATABASE_URL is required (environment or .env)")
    client = LLMClient.from_settings(settings)
    dims = dimensions or client.registry.embedding_dimensions(embedding_model)
    if dims is None:
        raise SystemExit(f"unknown dimension for {embedding_model!r}: pass --dimensions")
    documents = (
        qasper_documents(settings, max_docs)
        if dataset == "qasper"
        else beir_documents(settings, dataset, max_docs)
    )
    # --chunk-size 0: no cutting. The chunks then belong to another source key, since
    # the chunks of a source are shared by all its indexes.
    whole = chunk_size == 0
    chunker = (
        RecursiveChunker(chunk_size=NO_SPLIT, chunk_overlap=0)
        if whole
        else RecursiveChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    )
    async with PgVectorStore.from_url(settings.database_url) as store:
        pipeline = IngestionPipeline(
            client=client,
            store=store,
            chunker=chunker,
            data_class=DataClass.PUBLIC,
        )
        cut = "whole documents" if whole else f"recursive({chunk_size}/{chunk_overlap})"
        spec = pipeline.index_spec(
            index_key=index_key,
            source_key=f"docs:{dataset}:whole" if whole else f"docs:{dataset}",
            embedding_model=embedding_model,
            dimensions=dims,
            description=f"{dataset} / {cut} / {embedding_model}",
        )
        return await pipeline.ingest(spec, documents)


def main(argv: list[str] | None = None) -> int:
    load_env_file()  # .env at the repository root; the environment wins
    parser = argparse.ArgumentParser(description="Index a public dataset in pgvector.")
    parser.add_argument("dataset", choices=[*sorted(BEIR_DATASETS), "qasper"])
    parser.add_argument("--index-key", default=None)
    parser.add_argument("--embedding-model", default="openai/text-embedding-3-small")
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--chunk-size", type=int, default=1_000, help="0: do not cut")
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--max-docs", type=int, default=None, help="truncate (quick test)")
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
