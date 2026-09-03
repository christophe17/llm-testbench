"""Configuration du banc d'essai.

Deux modes d'exécution traversent tout le projet :

- **complet** (défaut) : les loaders téléchargent les jeux publics réels et le cache
  vit dans ``data/cache/``. C'est le mode qui produit des chiffres publiables.
- **échantillon** (``LLM_TESTBENCH_SAMPLE=1``) : quelques requêtes seulement, et si
  ``LLM_TESTBENCH_FIXTURES_DIR`` est défini, les loaders lisent des fixtures locales
  au lieu du réseau. C'est le mode CI : il vérifie que tout s'exécute, il ne produit
  jamais un chiffre. Cette séparation est un engagement du brief (section 2.B.4).
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_TESTBENCH_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data/cache")
    """Cache local des jeux publics (jamais versionné)."""

    sample: bool = False
    """Mode échantillon : jeux tronqués, exécution rapide, chiffres non publiables."""

    sample_max_queries: int = 5
    """Nombre de requêtes conservées en mode échantillon."""

    fixtures_dir: Path | None = None
    """Si défini, les loaders lisent ces fixtures locales au lieu du réseau (CI hors ligne)."""

    config_dir: Path | None = None
    """Répertoire des fichiers de configuration TOML (défaut : ``<racine du dépôt>/config``)."""

    prompts_dir: Path | None = None
    """Répertoire des prompts versionnés (défaut : ``<racine du dépôt>/prompts``)."""

    # ------------------------------------------------------------ API et stockage

    database_url: str | None = None
    """Postgres + pgvector. En local : ``make pg-port-forward`` puis
    ``postgresql://testbench:testbench-local-only@localhost:5432/testbench``."""

    chat_model: str | None = None
    """``backend/modèle`` du générateur ; défaut : ``defaults.generator`` du registre."""

    source_key: str = "docs:scifact"
    index_key: str = "scifact-recursive-oai-small"
    """L'index interrogé par l'API (registre ``indexes`` en base)."""

    retrieval_k: int = 5
    service_name: str = "llm-testbench-api"

    otlp_endpoint: str | None = None
    """Endpoint OTLP/HTTP des traces (Langfuse : ``<url>/api/public/otel/v1/traces``)."""

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
    """Remonte jusqu'à la racine du dépôt (marquée par pyproject.toml).

    Nécessaire aux notebooks, dont le répertoire courant est ``notebooks/``,
    pour ancrer chemins de cache et fixtures indépendamment d'où on exécute.
    """
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise FileNotFoundError(f"pas de pyproject.toml au-dessus de {current}")
