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
        "questions": 6,
        "sampled": False,
    }
    first, second = dataset.documents()
    assert first.title == "A Tiny Paper on Retrieval"
    assert [s.title for s in first.sections] == ["Abstract", "Introduction", "Method"]
    assert first.sections[1].text == "Retrieval finds documents.\n\nIt is the first step of RAG."
    assert first.source_uri == "hf:allenai/qasper/validation/1001.0001"
    assert first.metadata == {
        "dataset": "qasper",
        "split": "validation",
        "paper_id": "1001.0001",
    }
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


def test_questions_that_can_be_scored_from_the_text(loader: QasperLoader) -> None:
    dataset = loader.load_qa("validation")
    by_id = {example.example_id: example for example in dataset.examples}
    # q2: the annotators disagree on whether an answer exists. q6: its only evidence is a
    # table. Neither can be scored from the text.
    assert sorted(by_id) == ["q1", "q3", "q4", "q5"]
    first = by_id["q1"]
    # Two annotators, two wordings; their paragraphs pooled, the figure left out.
    assert first.answers == ("Retrieval", "Finding documents")
    assert [passage.text for passage in first.passages] == [
        "It is the first step of RAG.",
        "Retrieval finds documents.",
    ]
    assert first.passages[0].document_id == "1001.0001"
    assert first.scope == {"paper_id": "1001.0001"}
    assert first.kind == "extractive"
    assert (by_id["q3"].kind, by_id["q3"].answers) == ("abstractive", ("It splits documents",))
    assert (by_id["q5"].kind, by_id["q5"].answers) == ("yes_no", ("Yes",))
    unanswerable = by_id["q4"]
    assert not unanswerable.answerable
    assert unanswerable.passages == ()
    assert unanswerable.scope == {"paper_id": "1001.0002"}
    assert dataset.describe() == {
        "dataset": "qasper",
        "split": "validation",
        "examples": 4,
        "answerable": 3,
        "unanswerable": 1,
        "corpus_documents": 2,
    }


def test_a_balanced_draw_keeps_every_paper_in_the_corpus(loader: QasperLoader) -> None:
    drawn = loader.load_qa("validation", max_examples=2, seed=0)
    assert [example.answerable for example in drawn.examples].count(False) == 1
    assert drawn.subsample_seed == 0
    assert len(drawn.corpus) == 2
