"""Fixtures partagées : chargement des échantillons bruts sous tests/fixtures/.

Les fixtures sont des données SYNTHÉTIQUES qui reproduisent le schéma exact des
sources (colonnes HF, JSON bruts) — aucune donnée réelle n'est versionnée. Les
tests valident le parsing pur ; les téléchargements réels sont marqués
``network`` et exclus par défaut.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_json() -> Callable[[str], Any]:
    def _load(name: str) -> Any:
        return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))

    return _load
