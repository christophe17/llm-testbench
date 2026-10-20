"""Registry of LLM backends, loaded from ``config/llm_backends.toml`` (ADR 006).

The registry creates no network client: it describes. It can resolve a
``backend/model`` reference to the backend configuration, read the API key from the
environment, and refuse what does not exist or is disabled. The governance policy consumes
its metadata.
"""

import os
import tomllib
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from llm_testbench.config import Settings, get_settings
from llm_testbench.llm.errors import BackendDisabledError, UnknownBackendError
from llm_testbench.llm.governance import BackendGovernance
from llm_testbench.llm.types import ModelRef

BACKENDS_FILENAME = "llm_backends.toml"


class BackendKind(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC_BEDROCK = "anthropic_bedrock"


class StructuredOutputMode(StrEnum):
    NATIVE = "native"
    """The backend enforces a JSON schema itself (output guaranteed to match the schema)."""
    PROMPT = "prompt"
    """The schema is requested in the prompt, validation happens afterwards."""


class BackendConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: BackendKind
    api_key_env: str | None = None
    base_url: str | None = None
    region: str | None = None
    enabled: bool = True
    structured_output: StructuredOutputMode = StructuredOutputMode.PROMPT
    governance: BackendGovernance

    def api_key(self) -> str | None:
        """Key read from the environment at call time — never stored."""
        if self.api_key_env is None:
            return None
        return os.environ.get(self.api_key_env) or None


class Defaults(BaseModel):
    model_config = ConfigDict(frozen=True)

    generator: ModelRef
    judge: ModelRef | None = None
    embeddings: ModelRef | None = None

    @field_validator("generator", "judge", "embeddings", mode="before")
    @classmethod
    def _parse_refs(cls, value: object) -> object:
        return ModelRef.parse(value) if isinstance(value, str) else value


class Registry(BaseModel):
    model_config = ConfigDict(frozen=True)

    defaults: Defaults
    backends: dict[str, BackendConfig]

    @model_validator(mode="after")
    def _defaults_point_to_known_backends(self) -> "Registry":
        for label in ("generator", "judge", "embeddings"):
            ref: ModelRef | None = getattr(self.defaults, label)
            if ref is not None and ref.backend not in self.backends:
                raise ValueError(
                    f"defaults.{label} references an unknown backend: {ref.backend!r} "
                    f"(known: {sorted(self.backends)})"
                )
        return self

    @classmethod
    def load(cls, path: Path) -> "Registry":
        with path.open("rb") as handle:
            return cls.model_validate(tomllib.load(handle))

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "Registry":
        settings = settings if settings is not None else get_settings()
        return cls.load(settings.resolved_config_dir() / BACKENDS_FILENAME)

    def get(self, name: str) -> BackendConfig:
        try:
            return self.backends[name]
        except KeyError:
            raise UnknownBackendError(
                f"unknown backend: {name!r} (known: {sorted(self.backends)})"
            ) from None

    def resolve(self, ref: ModelRef | str) -> tuple[ModelRef, BackendConfig]:
        """Reference → (parsed reference, backend configuration), or a clear error."""
        model_ref = ModelRef.parse(ref) if isinstance(ref, str) else ref
        config = self.get(model_ref.backend)
        if not config.enabled:
            raise BackendDisabledError(
                f"backend {model_ref.backend!r} disabled in {BACKENDS_FILENAME}"
            )
        return model_ref, config
