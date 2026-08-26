"""Configuration du projet, chargée depuis l'environnement (préfixe ``LTB_``) et ``.env``.

Un seul point d'entrée : ``get_settings()``. Aucun module ne lit ``os.environ``
directement — c'est ce qui permettra plus tard de surcharger la config en test
et de la documenter en un seul endroit.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Le projet est toujours installé en editable : la racine du repo se déduit du
# fichier. Un chemin relatif au CWD casserait dès qu'un notebook (exécuté depuis
# notebooks/) télécharge des données.
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LTB_", env_file=".env", extra="ignore")

    # Racine du cache de données publiques ; jamais versionnée (cf. data/README.md).
    data_dir: Path = _REPO_ROOT / "data"

    @property
    def hf_cache_dir(self) -> Path:
        """Cache Hugging Face (datasets + hub), isolé sous data/ pour rester effaçable."""
        return self.data_dir / "hf"


@lru_cache
def get_settings() -> Settings:
    return Settings()
