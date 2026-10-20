"""Testbench configuration.

Two execution modes run through the whole project:

- **full** (default): the loaders download the real public datasets and the cache
  lives in ``data/cache/``. This is the mode that produces publishable numbers.
- **sample** (``LLM_TESTBENCH_SAMPLE=1``): only a few queries, and if
  ``LLM_TESTBENCH_FIXTURES_DIR`` is set, the loaders read local fixtures instead of
  the network. This is the CI mode: it checks that everything runs, it never produces
  a number. This separation is a commitment of the brief (section 2.B.4).
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_TESTBENCH_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data/cache")
    """Local cache of the public datasets (never versioned)."""

    sample: bool = False
    """Sample mode: truncated datasets, fast run, numbers not publishable."""

    sample_max_queries: int = 5
    """Number of queries kept in sample mode."""

    fixtures_dir: Path | None = None
    """If set, the loaders read these local fixtures instead of the network (offline CI)."""

    config_dir: Path | None = None
    """Directory of the TOML configuration files (default: ``<repository root>/config``)."""

    prompts_dir: Path | None = None
    """Directory of the versioned prompts (default: ``<repository root>/prompts``)."""

    # ------------------------------------------------------------ API and storage

    database_url: str | None = None
    """Postgres + pgvector. Locally: ``make pg-port-forward`` then
    ``postgresql://testbench:testbench-local-only@localhost:5432/testbench``."""

    chat_model: str | None = None
    """``backend/model`` of the generator; default: ``defaults.generator`` of the registry."""

    source_key: str = "docs:scifact"
    index_key: str = "scifact-recursive-oai-small"
    """The index queried by the API (``indexes`` registry in the database)."""

    retrieval_k: int = 5
    service_name: str = "llm-testbench-api"

    otlp_endpoint: str | None = None
    """OTLP/HTTP endpoint for traces (Langfuse: ``<url>/api/public/otel/v1/traces``)."""

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None

    def resolved_config_dir(self) -> Path:
        return self.config_dir if self.config_dir is not None else find_repo_root() / "config"

    def resolved_prompts_dir(self) -> Path:
        return self.prompts_dir if self.prompts_dir is not None else find_repo_root() / "prompts"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up to the repository root (marked by pyproject.toml).

    Needed by the notebooks, whose current directory is ``notebooks/phase-N/``, to
    anchor cache and fixture paths regardless of where they run from.
    """
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise FileNotFoundError(f"no pyproject.toml above {current}")
