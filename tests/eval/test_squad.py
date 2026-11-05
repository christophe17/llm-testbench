import pytest
from pydantic import ValidationError

from llm_testbench.config import Settings
from llm_testbench.eval.loaders.squad import SquadV2Loader
from llm_testbench.eval.qa import Passage, QAExample


def test_unanswerable_is_an_empty_answer_list(offline_settings: Settings) -> None:
    dataset = SquadV2Loader(offline_settings).load()
    by_id = {example.example_id: example for example in dataset.examples}
    assert by_id["q-river"].answerable
    # Annotators repeat the same wording: each wording is kept once.
    assert by_id["q-river"].answers == ("Massif Central", "the Massif Central")
    assert not by_id["q-length"].answerable
    assert by_id["q-length"].answers == ()
    assert dataset.describe() == {
        "dataset": "squad_v2",
        "split": "validation",
        "examples": 4,
        "answerable": 2,
        "unanswerable": 2,
    }


def test_gold_passage_becomes_numbered_evidence(offline_settings: Settings) -> None:
    example = SquadV2Loader(offline_settings).load().examples[0]
    (evidence,) = example.evidence("squad_v2")
    assert evidence.rank == 1
    assert evidence.text.startswith("The Loire is the longest river")
    assert evidence.provenance.label() == "squad_v2 › Loire › gold passage"


def test_subsample_is_balanced_seeded_and_declared(offline_settings: Settings) -> None:
    loader = SquadV2Loader(offline_settings)
    first = loader.load(max_examples=2, seed=1)
    assert [example.answerable for example in first.examples].count(True) == 1
    assert first.subsample_seed == 1
    assert first.describe()["subsample_seed"] == 1
    assert loader.load(max_examples=2, seed=1) == first
    # Larger than the split: the whole split, not a subsample.
    assert loader.load(max_examples=50).subsample_seed is None


def test_label_and_answers_must_agree() -> None:
    passage = Passage(passage_id="p", text="text")
    with pytest.raises(ValidationError, match="without a reference answer"):
        QAExample(example_id="x", question="q?", passages=(passage,))
    with pytest.raises(ValidationError, match="unanswerable with a reference answer"):
        QAExample(
            example_id="x", question="q?", passages=(passage,), answers=("a",), answerable=False
        )


@pytest.mark.network
def test_real_validation_split(tmp_path_factory: pytest.TempPathFactory) -> None:
    settings = Settings(data_dir=tmp_path_factory.mktemp("hf-cache"))
    dataset = SquadV2Loader(settings).load()
    assert dataset.describe()["examples"] == 11_873
    assert dataset.describe()["unanswerable"] == 5_945
