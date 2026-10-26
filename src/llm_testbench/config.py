"""Testbench configuration.

Two execution modes run through the whole project:

- **full** (default): the loaders download the real public datasets and the cache
  lives in ``data/cache/``. This is the mode that produces publishable numbers.
- **sample** (``LLM_TESTBENCH_SAMPLE=1``): only a few queries, and if
  ``LLM_TESTBENCH_FIXTURES_DIR`` is set, the loaders read local fixtures instead of
  the network. This is the CI mode: it checks that everything runs, it never produces
  a number. This separation is a commitment of the brief (section 2.B.4).

Local secrets and URLs live in ``.env`` at the repository root (see ``.env.example``). Nothing
reads that file implicitly: the entry points (ingestion CLI, embedding benchmark, API,
notebooks) call :func:`load_env_file` once at start-up, which exports its lines into the
process environment, and everything else — ``Settings`` as well as the provider keys read by
the backend registry at call time — sees plain environment variables. One file, one reader,
and the environment always wins over the file.
"""

import os
from collections.abc import MutableMapping
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_TESTBENCH_", extra="ignore")

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


def load_env_file(
    path: Path | None = None,
    *,
    override: bool = False,
    environ: MutableMapping[str, str] | None = None,
) -> list[str]:
    """Export the ``KEY=value`` lines of a ``.env`` file into the process environment.

    Why this exists: pydantic-settings only knows the ``LLM_TESTBENCH_*`` fields, while the
    provider keys (``OPENAI_API_KEY``...) are plain environment variables, read by the backend
    registry at call time and never stored (ADR 006). Without this call, a key written in
    ``.env`` is invisible to the providers: a half-loaded configuration, confusing to debug.

    Rules, deliberately few: blank lines and ``#`` comments are skipped, a leading ``export``
    and matching quotes are stripped, an empty value leaves the variable untouched, and a
    variable already set (non-empty) in the environment wins unless ``override`` is true, so a
    value injected by Kubernetes or CI is never shadowed by a stray ``.env``. Default path:
    ``.env`` at the repository root; no file, or no repository root (the container image), is
    a no-op.

    Returns the names of the variables that were set. Call it before the first
    :func:`get_settings`, which is cached.
    """
    target = environ if environ is not None else os.environ
    if path is None:
        try:
            path = find_repo_root() / ".env"
        except FileNotFoundError:
            return []
    if not path.is_file():
        return []
    loaded: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not key or not value:
            continue
        if override or not target.get(key):
            target[key] = value
            loaded.append(key)
    return loaded
