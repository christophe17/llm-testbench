"""Building the in-house corpus: harvest, select, download, write the manifest.

The selection has two criteria and two only (phase 2.5): the paper is **fresh** (first
submitted after the floor, under a license that allows quoting it) and **hard to parse**
(tables, footnotes, formulas, counted on the reference text). The topic is not a
criterion. Candidates are examined in the order of their identifiers and the first
``size`` that pass are kept: the same configuration selects the same papers, whoever
runs it.

Files go to the local cache (``data/cache/corpus/<name>/``), never to the repository; the
manifest records their hashes, and :class:`Corpus` refuses a file that does not match.

Two entry points. :func:`build_corpus` selects and writes the manifest: done once, and its
result is versioned. :func:`download_corpus` fetches the documents an existing manifest
lists: what anyone else runs. Selecting again later would not give the same papers (arXiv
lists records by their last modification, and papers get revised); downloading does.
"""

import datetime as dt
from collections.abc import Callable
from pathlib import Path

from llm_testbench.eval.corpus.arxiv import ArxivClient, ArxivRecord
from llm_testbench.eval.corpus.manifest import (
    CorpusConfig,
    Manifest,
    ManifestEntry,
    sha256_bytes,
)
from llm_testbench.eval.corpus.reference import ReferenceFeatures, reference_document
from llm_testbench.ingest.parsing import ParsedDocument
from llm_testbench.ingest.pdf import extract_pdf_naive

Echo = Callable[[str], None]


def is_candidate(record: ArxivRecord, config: CorpusConfig) -> bool:
    """Fresh, under the right license, in a kept category. The date compared is the one
    of the first version: a 2013 paper revised yesterday is not fresh."""
    return (
        record.license == config.license
        and record.submitted.date() >= config.freshness_floor
        and record.primary_category in config.categories
    )


def is_hard_enough(features: ReferenceFeatures, config: CorpusConfig) -> bool:
    return (
        features.difficulty >= config.min_difficulty
        and features.tables >= config.min_tables
        and features.footnotes >= config.min_footnotes
        and config.min_characters <= features.characters <= config.max_characters
    )


def corpus_dir(data_dir: Path, name: str) -> Path:
    return data_dir / "corpus" / name


def build_corpus(
    config: CorpusConfig,
    client: ArxivClient,
    directory: Path,
    *,
    echo: Echo = lambda _line: None,
) -> Manifest:
    """Select the corpus, download it into ``directory`` and return its manifest. Files
    already there are reused: an interrupted build resumes where it stopped."""
    directory.mkdir(parents=True, exist_ok=True)
    records = {
        record.arxiv_id: record
        for record in client.harvest(
            set_spec=config.set_spec, since=config.freshness_floor, until=config.harvest_until
        )
        if is_candidate(record, config)
    }
    echo(f"{len(records)} fresh candidates under {config.license}")
    entries: list[ManifestEntry] = []
    seen = 0
    for arxiv_id in sorted(records):
        if len(entries) >= config.size:
            break
        record = records[arxiv_id]
        seen += 1
        doc_id = f"{arxiv_id}v1"
        html_path = directory / f"{doc_id}.html"
        absent = directory / f"{doc_id}.no-html"
        if absent.is_file():
            continue
        # Every page fetched is kept, selected or not: choosing other thresholds must not
        # cost arXiv the same requests again.
        if html_path.is_file():
            html: str | None = html_path.read_text(encoding="utf-8")
        else:
            html = client.html(arxiv_id)
            if html is not None:
                html_path.write_text(html, encoding="utf-8")
        if html is None:
            absent.touch()
            echo(f"  {doc_id}: no HTML rendering, skipped")
            continue
        try:
            document, features = reference_document(html, doc_id, title=record.title)
        except ValueError as error:
            echo(f"  {error}, skipped")
            continue
        if not is_hard_enough(features, config):
            echo(
                f"  {doc_id}: not kept ({features.characters} characters, {features.tables} "
                f"tables, {features.footnotes} footnotes, {features.formulas} formulas)"
            )
            continue
        pdf_path = directory / f"{doc_id}.pdf"
        pdf = pdf_path.read_bytes() if pdf_path.is_file() else client.pdf(arxiv_id)
        if pdf is None:
            echo(f"  {doc_id}: no PDF, skipped")
            continue
        pdf_path.write_bytes(pdf)
        entries.append(
            ManifestEntry(
                arxiv_id=arxiv_id,
                version=1,
                title=record.title,
                authors=record.authors,
                categories=record.categories,
                license=record.license,
                submitted=record.submitted,
                reference_sha256=document.checksum,
                pdf_sha256=sha256_bytes(pdf),
                pdf_bytes=len(pdf),
                features=features,
            )
        )
        echo(
            f"  {doc_id}: kept ({features.tables} tables, {features.footnotes} footnotes, "
            f"{features.formulas} formulas) — {len(entries)}/{config.size}"
        )
    return Manifest(
        name=config.name,
        built_at=dt.datetime.now(dt.UTC),
        freshness_floor=config.freshness_floor,
        models=config.models,
        selection={
            "set_spec": config.set_spec,
            "harvest_until": config.harvest_until.isoformat(),
            "categories": list(config.categories),
            "license": config.license,
            "size": config.size,
            "min_difficulty": config.min_difficulty,
            "min_tables": config.min_tables,
            "min_footnotes": config.min_footnotes,
            "min_characters": config.min_characters,
            "max_characters": config.max_characters,
            "order": "ascending arXiv identifier, first that pass",
        },
        candidates_seen=seen,
        documents=tuple(entries),
    )


class Corpus:
    """The corpus as downloaded: the manifest, and the files it vouches for."""

    def __init__(self, manifest: Manifest, directory: Path) -> None:
        self.manifest = manifest
        self.directory = directory

    def pdf_path(self, entry: ManifestEntry) -> Path:
        """The PDF of a document, checked against the manifest."""
        path = self.directory / f"{entry.doc_id}.pdf"
        if not path.is_file():
            raise FileNotFoundError(f"{path} is missing: make corpus-download")
        if sha256_bytes(path.read_bytes()) != entry.pdf_sha256:
            raise ValueError(f"{path} does not match the manifest: it is not the file selected")
        return path

    def reference(self, entry: ManifestEntry) -> ParsedDocument:
        """The reference text of a document, checked against the manifest."""
        path = self.directory / f"{entry.doc_id}.html"
        if not path.is_file():
            raise FileNotFoundError(f"{path} is missing: make corpus-download")
        document, _ = reference_document(
            path.read_text(encoding="utf-8"), entry.doc_id, title=entry.title, source_uri=entry.url
        )
        if document.checksum != entry.reference_sha256:
            raise ValueError(f"{path} does not give the reference text the manifest recorded")
        return document

    def extracted(self, entry: ManifestEntry) -> ParsedDocument:
        """The document as the naive extractor reads its PDF (``ingest/pdf.py``): what
        the system as built indexes. Kept next to the PDF: extracting two hundred papers
        takes minutes, and the result only changes with the file."""
        cached = self.directory / f"{entry.doc_id}.pypdf.json"
        if cached.is_file():
            document = ParsedDocument.model_validate_json(cached.read_text(encoding="utf-8"))
            if document.metadata.get("pdf_sha256") == entry.pdf_sha256:
                return document
        document = extract_pdf_naive(
            self.pdf_path(entry),
            entry.doc_id,
            title=entry.title,
            source_uri=entry.url,
            metadata={"dataset": self.manifest.name, "pdf_sha256": entry.pdf_sha256},
        )
        cached.write_text(document.model_dump_json(), encoding="utf-8")
        return document

    def missing(self) -> list[str]:
        """Documents of the manifest whose files are absent or altered."""
        broken: list[str] = []
        for entry in self.manifest.documents:
            try:
                self.pdf_path(entry)
                self.reference(entry)
            except (FileNotFoundError, ValueError):
                broken.append(entry.doc_id)
        return broken


def download_corpus(
    manifest: Manifest,
    client: ArxivClient,
    directory: Path,
    *,
    echo: Echo = lambda _line: None,
) -> Corpus:
    """Fetch the documents of an existing manifest that are not in ``directory`` yet, then
    check every file. Raises ``ValueError`` if arXiv no longer serves what was selected."""
    directory.mkdir(parents=True, exist_ok=True)
    for entry in manifest.documents:
        html_path = directory / f"{entry.doc_id}.html"
        pdf_path = directory / f"{entry.doc_id}.pdf"
        if not html_path.is_file():
            html = client.html(entry.arxiv_id, entry.version)
            if html is None:
                raise ValueError(f"{entry.doc_id}: arXiv no longer serves its HTML rendering")
            html_path.write_text(html, encoding="utf-8")
            echo(f"  {entry.doc_id}: reference text downloaded")
        if not pdf_path.is_file():
            pdf = client.pdf(entry.arxiv_id, entry.version)
            if pdf is None:
                raise ValueError(f"{entry.doc_id}: arXiv no longer serves its PDF")
            pdf_path.write_bytes(pdf)
            echo(f"  {entry.doc_id}: PDF downloaded")
    corpus = Corpus(manifest, directory)
    broken = corpus.missing()
    if broken:
        raise ValueError(f"{len(broken)} documents do not match the manifest: {broken[:5]}")
    return corpus
