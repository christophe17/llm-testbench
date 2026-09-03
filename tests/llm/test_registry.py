from pathlib import Path

import pytest

from llm_testbench.llm.errors import BackendDisabledError, UnknownBackendError
from llm_testbench.llm.registry import BackendKind, Registry, StructuredOutputMode
from llm_testbench.llm.types import ModelRef

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKENDS_TOML = REPO_ROOT / "config" / "llm_backends.toml"


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.load(BACKENDS_TOML)


def test_real_config_declares_the_six_backend_roles(registry: Registry) -> None:
    assert set(registry.backends) == {"anthropic", "openai", "openrouter", "bedrock", "local"}
    assert registry.get("anthropic").kind is BackendKind.ANTHROPIC
    assert registry.get("openrouter").kind is BackendKind.OPENAI_COMPATIBLE
    assert registry.get("openrouter").structured_output is StructuredOutputMode.PROMPT
    assert registry.get("bedrock").kind is BackendKind.ANTHROPIC_BEDROCK


def test_default_generator_resolves(registry: Registry) -> None:
    assert registry.defaults.generator == ModelRef(backend="anthropic", model="claude-sonnet-5")
    ref, config = registry.resolve(str(registry.defaults.generator))
    assert ref.model == "claude-sonnet-5"
    assert config.api_key_env == "ANTHROPIC_API_KEY"


def test_unknown_backend_is_a_typed_error(registry: Registry) -> None:
    with pytest.raises(UnknownBackendError, match="connus"):
        registry.resolve("nowhere/model")


def test_disabled_backend_is_refused_until_enabled(registry: Registry) -> None:
    assert registry.get("bedrock").enabled is False
    with pytest.raises(BackendDisabledError, match="bedrock"):
        registry.resolve("bedrock/anthropic.claude-sonnet-5")


def test_api_key_is_read_from_environment_at_call_time(
    registry: Registry, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = registry.get("anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert config.api_key() is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert config.api_key() == "sk-test"
    assert registry.get("local").api_key() is None


def test_defaults_must_point_to_declared_backends() -> None:
    data = Registry.load(BACKENDS_TOML).model_dump()
    data["defaults"]["generator"] = "ghost/model"
    with pytest.raises(ValueError, match="backend inconnu"):
        Registry.model_validate(data)
