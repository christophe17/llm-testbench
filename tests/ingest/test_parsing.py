from llm_testbench.ingest.parsing import parse_markdown, parse_sections, parse_text

MARKDOWN = """Préambule avant tout titre.

# Titre du document

Intro sous le titre.

## Méthode

Première ligne.
Deuxième ligne.

## Vide

## Résultats

Des chiffres.
"""


def test_parse_text_is_one_untitled_section() -> None:
    document = parse_text("d1", "  Bonjour.  ", title=" T ")
    assert document.title == "T"
    assert [(s.title, s.text, s.order) for s in document.sections] == [("", "Bonjour.", 0)]
    assert document.text == "Bonjour."
    assert document.char_count == 8


def test_parse_markdown_splits_on_headings_and_drops_empty_sections() -> None:
    document = parse_markdown("d2", MARKDOWN)
    assert document.title == "Titre du document"
    assert [(s.title, s.order) for s in document.sections] == [
        ("", 0),
        ("Titre du document", 1),
        ("Méthode", 2),
        ("Résultats", 3),
    ]
    assert document.sections[2].text == "Première ligne.\nDeuxième ligne."
    assert parse_markdown("d3", MARKDOWN, title="Forcé").title == "Forcé"


def test_parse_sections_keeps_order_and_metadata() -> None:
    document = parse_sections(
        "d4",
        [("Abstract", "Résumé."), ("Empty", "   "), ("Body", "Corps.")],
        title="Papier",
        source_uri="hf:allenai/qasper",
        metadata={"split": "validation"},
    )
    assert [s.title for s in document.sections] == ["Abstract", "Body"]
    assert document.source_uri == "hf:allenai/qasper"
    assert document.metadata == {"split": "validation"}


def test_checksum_changes_with_content_not_with_metadata() -> None:
    base = parse_text("d", "x", title="t")
    assert base.checksum == parse_text("d", "x", title="t", metadata={"a": "b"}).checksum
    assert base.checksum != parse_text("d", "y", title="t").checksum
    assert base.checksum != parse_text("d", "x", title="u").checksum
