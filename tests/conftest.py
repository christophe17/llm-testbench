from pathlib import Path

import pytest

from llm_testbench.config import Settings

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def offline_settings(tmp_path: Path) -> Settings:
    """Settings pointant sur les fixtures locales : aucun test ne touche le réseau."""
    return Settings(fixtures_dir=FIXTURES_DIR, data_dir=tmp_path / "cache")
