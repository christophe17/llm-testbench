"""The reference text of a paper: what a perfect parser would have extracted.

The in-house corpus is made of PDFs, and a PDF does not contain text in reading order: it
contains glyphs at coordinates. Whatever extracts text from it (the naive extractor of
phase 2, the parsers phase 3 will compare) makes mistakes: columns read across, table cells
run together, footnotes dropped in the middle of a sentence. To measure those mistakes, and
to write questions whose answers do not depend on them, each document needs a text that
did not go through a PDF parser.

arXiv provides one: since 2023 it renders the LaTeX source of a paper to HTML (LaTeXML),
with sections, paragraphs, tables and footnotes as explicit elements. This module turns
that page into a :class:`~llm_testbench.ingest.parsing.ParsedDocument`: one section per
heading, paragraphs separated by blank lines, a table as one line per row with ``|``
between cells, a footnote moved out of its sentence and placed after the paragraph,
formulas as their LaTeX source. The bibliography is left out: nothing in it is asked about.

It is a reference, not a truth: LaTeXML fails on some macros, and a paper it cannot render
has no page at all (such papers are not selected). It also counts what makes a document
hard to parse (tables, footnotes, formulas, figures), which is how the corpus is chosen.
"""

from html.parser import HTMLParser

from pydantic import BaseModel, ConfigDict

from llm_testbench.ingest.parsing import ParsedDocument, parse_sections

_VOID = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
)
_SECTION_CLASSES = ("ltx_section", "ltx_appendix", "ltx_subsection", "ltx_subsubsection")
_SKIPPED_CLASSES = ("ltx_bibliography", "ltx_page_footer", "ltx_page_header", "ltx_TOC")


class Node:
    """An element of the page: its tag, its classes, its children (elements or strings)."""

    def __init__(self, tag: str, attrs: dict[str, str]) -> None:
        self.tag = tag
        self.attrs = attrs
        self.classes = frozenset(attrs.get("class", "").split())
        self.children: list[Node | str] = []

    def has(self, *classes: str) -> bool:
        return any(name in self.classes for name in classes)

    def elements(self) -> list["Node"]:
        return [child for child in self.children if isinstance(child, Node)]

    def find_all(self, *classes: str) -> list["Node"]:
        """Every descendant carrying one of ``classes``, in document order."""
        found: list[Node] = []
        for child in self.elements():
            if child.has(*classes):
                found.append(child)
            found.extend(child.find_all(*classes))
        return found


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("root", {})
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {name: value or "" for name, value in attrs})
        self._stack[-1].children.append(node)
        if tag not in _VOID:
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        # Close up to the nearest open element of that name; a stray end tag is ignored.
        for depth in range(len(self._stack) - 1, 0, -1):
            if self._stack[depth].tag == tag:
                del self._stack[depth:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)


def parse_html(html: str) -> Node:
    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder.root


class ReferenceFeatures(BaseModel):
    """What makes a document hard to parse, counted on its reference text."""

    model_config = ConfigDict(frozen=True)

    sections: int
    characters: int
    tables: int
    footnotes: int
    formulas: int
    """Displayed formulas (the ones on their own line), not the inline ones."""
    figures: int

    @property
    def difficulty(self) -> int:
        """One number to rank candidates: each table, footnote and displayed formula is a
        place where a PDF extraction goes wrong."""
        return self.tables + self.footnotes + self.formulas


def _squash(text: str) -> str:
    return " ".join(text.split())


def _inline(node: Node, footnotes: list[str]) -> str:
    """The text of an element as one line. A formula gives its LaTeX source; a footnote is
    taken out of the sentence and collected in ``footnotes``."""
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        elif child.tag == "math":
            parts.append(child.attrs.get("alttext", ""))
        elif child.has("ltx_note_mark", "ltx_tag_note"):
            # The footnote number, repeated by LaTeXML in the sentence and in the note.
            continue
        elif child.has("ltx_note"):
            content = child.find_all("ltx_note_content")
            footnotes.append(_squash(_inline(content[0] if content else child, [])))
        elif child.tag in ("script", "style", "annotation", "annotation-xml"):
            continue
        else:
            parts.append(_inline(child, footnotes))
    return "".join(parts)


def _table(node: Node) -> str:
    """One line per row, cells separated by ``|``."""
    rows = []
    for row in node.find_all("ltx_tr"):
        cells = [
            _squash(_inline(cell, [])) for cell in row.elements() if cell.has("ltx_td", "ltx_th")
        ]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


class _Reader:
    """Walks the page and writes the sections of the reference text."""

    def __init__(self) -> None:
        self.sections: list[tuple[str, list[str]]] = []
        self.tables = self.footnotes = self.formulas = self.figures = 0

    def _blocks(self) -> list[str]:
        if not self.sections:
            self.sections.append(("", []))
        return self.sections[-1][1]

    def _paragraph(self, node: Node) -> None:
        notes: list[str] = []
        text = _squash(_inline(node, notes))
        if text:
            self._blocks().append(text)
        for note in notes:
            self.footnotes += 1
            self._blocks().append(f"[footnote] {note}")

    def _caption(self, node: Node) -> None:
        for caption in node.find_all("ltx_caption"):
            self._paragraph(caption)

    def walk(self, node: Node) -> None:
        for child in node.elements():
            if child.has(*_SKIPPED_CLASSES) or child.tag in ("script", "style", "nav", "head"):
                continue
            if child.has("ltx_abstract"):
                self.sections.append(("Abstract", []))
                self.walk(child)
            elif child.has(*_SECTION_CLASSES):
                self.sections.append(("", []))
                self.walk(child)
            elif child.has("ltx_title"):
                title = _squash(_inline(child, []))
                if child.has("ltx_title_document", "ltx_title_abstract"):
                    continue
                if self.sections and not self.sections[-1][0] and not self.sections[-1][1]:
                    self.sections[-1] = (title, [])
                elif title:
                    # A run-in heading (\paragraph{...}): kept as a line of its section.
                    self._blocks().append(title)
            elif child.has("ltx_table"):
                self.tables += 1
                self._caption(child)
                for tabular in child.find_all("ltx_tabular"):
                    text = _table(tabular)
                    if text:
                        self._blocks().append(text)
            elif child.has("ltx_figure"):
                self.figures += 1
                self._caption(child)
            elif child.has("ltx_equation", "ltx_equationgroup"):
                self.formulas += 1
                self._paragraph(child)
            elif child.has("ltx_p") or child.tag == "p":
                self._paragraph(child)
            elif child.has("ltx_authors", "ltx_dates", "ltx_classification", "ltx_keywords"):
                continue
            else:
                self.walk(child)


def reference_document(
    html: str, doc_id: str, *, title: str = "", source_uri: str | None = None
) -> tuple[ParsedDocument, ReferenceFeatures]:
    """The reference text of an arXiv HTML page, and what makes the paper hard to parse.
    Raises ``ValueError`` when the page holds no article (a paper LaTeXML could not render
    is served as an error page)."""
    root = parse_html(html)
    articles = root.find_all("ltx_document")
    if not articles:
        raise ValueError(f"{doc_id}: no LaTeXML article in the page")
    reader = _Reader()
    reader.walk(articles[0])
    document = parse_sections(
        doc_id,
        [(name, "\n\n".join(blocks)) for name, blocks in reader.sections],
        title=title,
        source_uri=source_uri,
        metadata={"dataset": "arxiv-fresh", "text": "reference"},
    )
    if not document.sections:
        raise ValueError(f"{doc_id}: the article has no text")
    return document, ReferenceFeatures(
        sections=len(document.sections),
        characters=document.char_count,
        tables=reader.tables,
        footnotes=reader.footnotes,
        formulas=reader.formulas,
        figures=reader.figures,
    )
