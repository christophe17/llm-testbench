"""The in-house corpus offline: arXiv metadata, the reference text, selection, manifest."""

import datetime as dt
from pathlib import Path

import pytest
from pydantic import ValidationError

from llm_testbench.eval.corpus.arxiv import (
    CC_BY_4,
    HTML_URL,
    PDF_URL,
    ArxivClient,
    offline_fetch,
    parse_records,
)
from llm_testbench.eval.corpus.build import Corpus, build_corpus, download_corpus, is_candidate
from llm_testbench.eval.corpus.manifest import CorpusConfig, Manifest, ModelFreshness
from llm_testbench.eval.corpus.reference import reference_document
from tests.conftest import FIXTURES_DIR

ARXIV = FIXTURES_DIR / "arxiv"
PAPER = (ARXIV / "2610.00001v1.html").read_text(encoding="utf-8")
PLAIN = (
    '<article class="ltx_document"><section class="ltx_section">'
    '<h2 class="ltx_title ltx_title_section">1 Only</h2>'
    '<p class="ltx_p">Nothing here is hard to extract.</p></section></article>'
)
PDF = b"%PDF-1.7 a fake file, only its hash matters here"


def config(**overrides: object) -> CorpusConfig:
    values: dict[str, object] = {
        "name": "unit",
        "freshness_floor": dt.date(2026, 10, 20),
        "harvest_until": dt.date(2026, 11, 4),
        "models": {
            "claude-sonnet-5-5": ModelFreshness(
                available_by=dt.date(2026, 10, 19), evidence="unit test"
            )
        },
        "categories": ("cs.CL",),
        "license": CC_BY_4,
        "size": 5,
        "min_tables": 2,
        "min_footnotes": 2,
        "max_characters": 10_000,
    }
    values.update(overrides)
    return CorpusConfig.model_validate(values)


class FakeArxiv:
    """arXiv, offline: two pages of metadata, one rendered paper, one plain paper."""

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.pages = {
            HTML_URL.format(arxiv_id="2610.00001", version=1): PAPER.encode(),
            HTML_URL.format(arxiv_id="2610.00003", version=1): PLAIN.encode(),
            PDF_URL.format(arxiv_id="2610.00001", version=1): PDF,
        }

    def __call__(self, url: str) -> bytes | None:
        self.urls.append(url)
        if "verb=ListRecords" in url:
            name = "oai_page_2.xml" if "resumptionToken" in url else "oai_page.xml"
            return (ARXIV / name).read_bytes()
        return self.pages.get(url)


def client(fake: FakeArxiv) -> ArxivClient:
    return ArxivClient(fetch=fake, sleep=lambda _seconds: None)


def test_a_record_carries_its_license_and_the_date_of_its_first_version() -> None:
    records, token = parse_records((ARXIV / "oai_page.xml").read_bytes())
    assert token == "token-page-2"
    # The deleted record has no metadata and is skipped.
    assert [record.arxiv_id for record in records] == ["2610.00001", "1307.02827", "2610.00002"]
    fresh, revised, closed = records
    assert fresh.title == "A Fresh Paper With Tables"
    assert (fresh.primary_category, fresh.license) == ("cs.CL", CC_BY_4)
    assert fresh.submitted.date() == dt.date(2026, 10, 21)
    # Revised in 2026, first submitted in 2013: the date that counts is the first one.
    assert (revised.versions, revised.submitted.year) == (2, 2013)
    assert not is_candidate(revised, config())
    assert not is_candidate(closed, config())
    assert is_candidate(fresh, config())


def test_harvest_follows_the_pages_and_waits_between_requests() -> None:
    fake = FakeArxiv()
    waits: list[float] = []
    harvester = ArxivClient(fetch=fake, sleep=waits.append, delay_s=3.0)
    records = list(harvester.harvest(set_spec="cs", since=dt.date(2026, 10, 20)))
    assert len(records) == 5
    assert len(fake.urls) == 2
    assert "resumptionToken=token-page-2" in fake.urls[1]
    assert len(waits) == 1
    assert 0 < waits[0] <= 3.0


def test_reference_text_keeps_tables_as_rows_and_moves_footnotes_out() -> None:
    document, features = reference_document(PAPER, "2610.00001v1", title="A Fresh Paper")
    assert [section.title for section in document.sections] == [
        "Abstract",
        "1 Introduction",
        "2 Results",
        "2.1 Cost",
    ]
    introduction, results, cost = document.sections[1:]
    # The footnote is out of the sentence, the formula is its LaTeX source.
    assert introduction.text.startswith(
        "Dense retrieval beats BM25 when k=10.\n\n[footnote] Code at example.org."
    )
    assert "Retriever | Recall\nBM25 | 0.61\nDense | 0.74" in results.text
    assert "Table 2: Latency in milliseconds." in results.text
    assert cost.text.endswith("c=n\\cdot p\n\nFigure 1: Cost against size.")
    # Neither the bibliography nor arXiv's header and footer are part of the text.
    assert "Okapi" not in document.text
    assert "LaTeXML" not in document.text
    assert (features.tables, features.footnotes, features.formulas, features.figures) == (
        2,
        2,
        1,
        1,
    )
    assert features.difficulty == 5


def test_a_page_without_an_article_is_not_a_reference() -> None:
    with pytest.raises(ValueError, match="no LaTeXML article"):
        reference_document("<html><body>Conversion failed.</body></html>", "x")


def test_the_selection_keeps_fresh_reusable_hard_documents(tmp_path: Path) -> None:
    fake = FakeArxiv()
    lines: list[str] = []
    manifest = build_corpus(config(), client(fake), tmp_path, echo=lines.append)
    # Five records: one old, one under another license, one in another field (never
    # fetched), one with nothing to break (fetched, not kept), one kept.
    assert [entry.doc_id for entry in manifest.documents] == ["2610.00001v1"]
    assert manifest.candidates_seen == 2
    assert not any("2610.00004" in url or "1307.02827" in url for url in fake.urls[2:])
    entry = manifest.documents[0]
    assert entry.authors == "Ada Lovelace, Charles Babbage"
    assert entry.url == "https://arxiv.org/abs/2610.00001v1"
    assert entry.features.tables == 2
    assert (tmp_path / "2610.00001v1.pdf").read_bytes() == PDF
    # The page of the paper that was not kept stays in the cache, without a PDF: another
    # selection would not ask arXiv for it again.
    assert (tmp_path / "2610.00003v1.html").exists()
    assert not (tmp_path / "2610.00003v1.pdf").exists()
    assert any("2610.00003v1: not kept" in line for line in lines)
    assert any("kept (2 tables, 2 footnotes, 1 formulas) — 1/5" in line for line in lines)
    fake.urls.clear()
    again = build_corpus(config(), client(fake), tmp_path)
    assert again.documents == manifest.documents
    assert not any("/html/" in url or "/pdf/" in url for url in fake.urls)


def test_the_manifest_vouches_for_the_files(tmp_path: Path) -> None:
    manifest = build_corpus(config(), client(FakeArxiv()), tmp_path / "first")
    path = tmp_path / "manifest.json"
    manifest.save(path)
    assert Manifest.load(path) == manifest
    # Someone else, later: the manifest alone is enough to fetch the same documents.
    fake = FakeArxiv()
    corpus = download_corpus(Manifest.load(path), client(fake), tmp_path / "second")
    assert not any("verb=ListRecords" in url for url in fake.urls)
    entry = corpus.manifest.documents[0]
    assert corpus.reference(entry).sections[0].title == "Abstract"
    assert corpus.missing() == []
    # arXiv's header changing does not alter the reference text; the paper changing does.
    page = tmp_path / "second" / "2610.00001v1.html"
    page.write_text(PAPER.replace("arXiv header that changes", "a new banner"), encoding="utf-8")
    assert corpus.missing() == []
    page.write_text(PAPER.replace("0.74", "0.99"), encoding="utf-8")
    assert corpus.missing() == ["2610.00001v1"]
    with pytest.raises(ValueError, match="does not give the reference text"):
        corpus.reference(entry)
    (tmp_path / "second" / "2610.00001v1.pdf").unlink()
    with pytest.raises(FileNotFoundError, match="make corpus-download"):
        Corpus(corpus.manifest, tmp_path / "second").pdf_path(entry)


def test_freshness_is_established_per_model_never_assumed(tmp_path: Path) -> None:
    manifest = build_corpus(config(), client(FakeArxiv()), tmp_path)
    assert manifest.fresh_for("anthropic/claude-sonnet-5-5")
    assert manifest.fresh_for("claude-sonnet-5-5")
    # A model the manifest does not know may be newer than the documents.
    assert not manifest.fresh_for("anthropic/claude-sonnet-6")
    # A floor that is not after every listed model is refused when the file is loaded.
    with pytest.raises(ValidationError, match="not after these models"):
        config(freshness_floor=dt.date(2026, 10, 19))


def test_the_versioned_selection_is_valid() -> None:
    selection = CorpusConfig.load(Path(__file__).resolve().parents[3] / "config" / "corpus.toml")
    assert selection.license == CC_BY_4
    assert selection.freshness_floor > max(m.available_by for m in selection.models.values())
    assert {"claude-sonnet-5-5", "gpt-5.6-luna"} <= set(selection.models)


def test_the_offline_stand_in_serves_the_fixture_files(tmp_path: Path) -> None:
    fetch = offline_fetch(ARXIV)
    manifest = build_corpus(config(), ArxivClient(fetch=fetch, sleep=lambda _s: None), tmp_path)
    # Same selection as on the scripted network: one paper kept, with its real little PDF.
    assert [entry.doc_id for entry in manifest.documents] == ["2610.00001v1"]
    corpus = Corpus(manifest, tmp_path)
    pages = corpus.extracted(manifest.documents[0])
    assert [section.title for section in pages.sections] == ["Page 1", "Page 2"]
    # The PDF holds the footnote where the page drew it: after the last line, mark glued on.
    assert pages.sections[0].text.endswith("1Code at example.org.")
    assert fetch("https://example.org/elsewhere") is None
