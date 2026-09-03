import hashlib
from pathlib import Path

import pytest

from llm_testbench.llm.errors import PromptError
from llm_testbench.llm.prompts import PromptRegistry, parse_prompt_file

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "prompts"


@pytest.fixture
def registry() -> PromptRegistry:
    return PromptRegistry(FIXTURES)


def test_header_and_body_are_parsed(registry: PromptRegistry) -> None:
    template = registry.get("greeting")
    assert (template.name, template.version) == ("greeting", 2)
    assert template.description == "Prompt de test pour le registre."
    assert template.body == "Bonjour {{ name }}, tu as {{ count }} messages."
    assert registry.names() == ["greeting"]


def test_render_fills_variables_and_fingerprints_the_exact_text(registry: PromptRegistry) -> None:
    rendered = registry.render("greeting", name="Ada", count=3)
    assert rendered.text == "Bonjour Ada, tu as 3 messages."
    assert rendered.sha256 == hashlib.sha256(rendered.text.encode()).hexdigest()
    assert rendered.sha256 == registry.render("greeting", name="Ada", count=3).sha256
    assert rendered.sha256 != registry.render("greeting", name="Ada", count=4).sha256
    assert rendered.template_sha256 == registry.get("greeting").source_sha256
    assert rendered.trace_metadata()["prompt.version"] == "2"


def test_missing_variable_is_an_error_not_an_empty_string(registry: PromptRegistry) -> None:
    with pytest.raises(PromptError, match="count"):
        registry.render("greeting", name="Ada")


def test_unknown_prompt_is_an_error(registry: PromptRegistry) -> None:
    with pytest.raises(PromptError, match="introuvable"):
        registry.get("nope")


def test_invalid_headers_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("no header at all", encoding="utf-8")
    with pytest.raises(PromptError, match="en-tête"):
        parse_prompt_file(tmp_path / "a.md")
    (tmp_path / "b.md").write_text("---\nname: other\nversion: 1\n---\nx", encoding="utf-8")
    with pytest.raises(PromptError, match="nom du fichier"):
        parse_prompt_file(tmp_path / "b.md")
    (tmp_path / "c.md").write_text("---\nname: c\nversion: zero\n---\nx", encoding="utf-8")
    with pytest.raises(PromptError, match="en-tête invalide"):
        parse_prompt_file(tmp_path / "c.md")


def test_template_syntax_error_is_reported_with_prompt_name(tmp_path: Path) -> None:
    (tmp_path / "d.md").write_text("---\nname: d\nversion: 1\n---\n{% if %}", encoding="utf-8")
    with pytest.raises(PromptError, match="'d' v1"):
        PromptRegistry(tmp_path).render("d")


def test_every_real_prompt_parses() -> None:
    registry = PromptRegistry(REPO_ROOT / "prompts")
    for name in registry.names():
        assert registry.get(name).version >= 1
