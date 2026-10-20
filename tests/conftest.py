from pathlib import Path

import pytest

from llm_testbench.config import Settings

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def offline_settings(tmp_path: Path) -> Settings:
    """Settings pointing to the local fixtures: no test touches the network."""
    return Settings(fixtures_dir=FIXTURES_DIR, data_dir=tmp_path / "cache")
