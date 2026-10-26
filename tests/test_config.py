"""Tests of the configuration: the ``.env`` loader and the single-reader rule."""

from pathlib import Path

import pytest

from llm_testbench.config import Settings, find_repo_root, load_env_file


def test_load_env_file_parses_the_dev_file_format(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "\n"
        "OPENAI_API_KEY=sk-o\n"
        "export ANTHROPIC_API_KEY='sk-a'\n"
        'LLM_TESTBENCH_DATABASE_URL = "postgresql://u:p@localhost/db"\n'
        "OPENROUTER_API_KEY=\n"
        "not a variable\n"
    )
    environ: dict[str, str] = {}
    loaded = load_env_file(env_file, environ=environ)
    assert loaded == ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_TESTBENCH_DATABASE_URL"]
    assert environ == {
        "OPENAI_API_KEY": "sk-o",
        "ANTHROPIC_API_KEY": "sk-a",
        "LLM_TESTBENCH_DATABASE_URL": "postgresql://u:p@localhost/db",
    }


def test_load_env_file_never_shadows_the_environment(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=from-file\nANTHROPIC_API_KEY=from-file\n")
    environ = {"OPENAI_API_KEY": "from-shell", "ANTHROPIC_API_KEY": ""}
    assert load_env_file(env_file, environ=environ) == ["ANTHROPIC_API_KEY"]
    assert environ["OPENAI_API_KEY"] == "from-shell"
    assert environ["ANTHROPIC_API_KEY"] == "from-file"  # an empty variable counts as unset
    overridden = load_env_file(env_file, override=True, environ=environ)
    assert overridden == ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    assert environ["OPENAI_API_KEY"] == "from-file"


def test_load_env_file_is_a_no_op_without_file_or_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environ: dict[str, str] = {}
    assert load_env_file(tmp_path / "absent.env", environ=environ) == []
    monkeypatch.chdir(tmp_path)  # no pyproject.toml above: the container image case
    with pytest.raises(FileNotFoundError):
        find_repo_root()
    assert load_env_file(environ=environ) == []
    assert environ == {}


def test_settings_do_not_read_env_files_themselves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("LLM_TESTBENCH_RETRIEVAL_K=99\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLM_TESTBENCH_RETRIEVAL_K", raising=False)
    assert Settings().retrieval_k == 5
