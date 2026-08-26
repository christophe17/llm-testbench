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
