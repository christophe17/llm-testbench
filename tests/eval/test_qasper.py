from pathlib import Path

import pytest

from llm_testbench.config import Settings
from llm_testbench.eval.loaders.qasper import QasperLoader

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def loader(tmp_path: Path) -> QasperLoader:
    return QasperLoader(Settings(fixtures_dir=FIXTURES, data_dir=tmp_path))


def test_papers_become_sectioned_documents(loader: QasperLoader) -> None:
    dataset = loader.load("validation")
    assert dataset.describe() == {
        "dataset": "qasper",
        "split": "validation",
        "papers": 2,
        "sections": 3,
        "questions": 3,
        "sampled": False,
    }
    first, second = dataset.documents()
    assert first.title == "A Tiny Paper on Retrieval"
    assert [s.title for s in first.sections] == ["Abstract", "Introduction", "Method"]
    assert first.sections[1].text == "Retrieval finds documents.\n\nIt is the first step of RAG."
    assert first.source_uri == "hf:allenai/qasper/validation/1001.0001"
    assert first.metadata == {"dataset": "qasper", "split": "validation"}
    assert [s.title for s in second.sections] == ["Abstract", "Body"]
    assert dataset.papers[1].questions[0].question_id == "q3"


def test_sample_mode_truncates_and_flags(loader: QasperLoader) -> None:
    dataset = loader.load("validation", max_papers=1)
    assert dataset.sampled is True
    assert len(dataset.papers) == 1
    assert loader.load("validation", max_papers=5).sampled is False


def test_missing_fixture_is_loud(loader: QasperLoader) -> None:
    with pytest.raises(FileNotFoundError, match=r"test\.json"):
        loader.load("test")


@pytest.mark.network
def test_real_validation_split_matches_the_published_size(tmp_path: Path) -> None:
    dataset = QasperLoader(Settings(data_dir=tmp_path / "cache")).load("validation")
    assert len(dataset.papers) == 281
    assert all(p.sections for p in dataset.papers)
