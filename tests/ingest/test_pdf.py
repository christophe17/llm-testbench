"""The naive PDF extractor, on a PDF small enough to be written by hand."""

from pathlib import Path

from llm_testbench.ingest.pdf import extract_pdf_naive


def tiny_pdf(pages: list[list[str]]) -> bytes:
    """A valid PDF with one text line per string, in the order given. An empty list
    makes a page with nothing drawn on it."""
    objects: list[bytes] = []
    page_ids = [4 + 2 * index for index in range(len(pages))]
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for page_id, lines in zip(page_ids, pages, strict=True):
        drawn = "".join(f"({line}) Tj 0 -14 Td " for line in lines)
        stream = f"BT /F1 12 Tf 72 720 Td {drawn}ET".encode() if lines else b""
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {page_id + 1} 0 R >>".encode()
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    body = b"%PDF-1.4\n"
    offsets = []
    for number, content in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{number} 0 obj\n".encode() + content + b"\nendobj\n"
    xref = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    body += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    body += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return body


def test_one_section_per_page_in_the_order_the_page_was_drawn(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    # A table drawn cell by cell, then a footnote at the bottom of the page: the PDF
    # holds them in drawing order, and so does the extraction.
    path.write_bytes(
        tiny_pdf(
            [
                ["Retriever", "Recall", "BM25", "0.61", "1 Code at example.org."],
                [],
                ["Second page of text."],
            ]
        )
    )
    document = extract_pdf_naive(path, "2610.00001v1", title="A Fresh Paper")
    # The page with nothing on it is dropped; the others keep their page number.
    assert [section.title for section in document.sections] == ["Page 1", "Page 3"]
    first = document.sections[0].text
    assert first.index("Retriever") < first.index("0.61") < first.index("Code at example.org")
    assert "|" not in first
    assert document.sections[1].text == "Second page of text."
    assert document.metadata == {"parser": "pypdf-naive"}
    assert document.title == "A Fresh Paper"
