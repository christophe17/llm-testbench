"""PDF to text, the naive way: the baseline every parser of phase 3 has to beat.

A PDF stores glyphs at coordinates, not text in reading order. The simplest thing that
gives text back is to ask a library for "the text of the page" and take what comes:
``pypdf`` walks the content stream and emits characters in the order they were drawn.
On a two-column paper with tables, footnotes and formulas, that order is not the reading
order, and nothing here tries to fix it:

- a table comes out as its cells one after another, without rows or columns;
- a footnote lands wherever the page drew it, usually after the last line of a column;
- a formula becomes a run of symbols, its fractions and indices flattened;
- words hyphenated at a line end stay cut, headers and page numbers stay in the text;
- there are no sections: the only structure a PDF gives for free is the page.

That is the point. Phase 2 ingests the in-house corpus through this extractor, so that
the baseline of the system is the one a first version of any RAG would have; phase 3
measures what a real parser gains over it, against the reference text of each document
(``eval/corpus/reference.py``).
"""

from pathlib import Path

from llm_testbench.ingest.parsing import ParsedDocument, parse_sections


def extract_pdf_naive(
    path: Path,
    doc_id: str,
    *,
    title: str = "",
    source_uri: str | None = None,
    metadata: dict[str, str] | None = None,
) -> ParsedDocument:
    """One section per page, named ``Page N``, holding whatever ``pypdf`` returns for it.
    A page without extractable text (a scan, a full-page figure) is dropped."""
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = [
        (f"Page {number}", page.extract_text() or "")
        for number, page in enumerate(reader.pages, start=1)
    ]
    return parse_sections(
        doc_id,
        pages,
        title=title,
        source_uri=source_uri,
        metadata={"parser": "pypdf-naive", **(metadata or {})},
    )
