import pytest

from llm_testbench.config import Settings
from llm_testbench.eval.loaders import BeirLoader


@pytest.fixture
def loader(offline_settings: Settings) -> BeirLoader:
    return BeirLoader("scifact", settings=offline_settings)


def test_unknown_beir_dataset_rejected() -> None:
    with pytest.raises(ValueError, match="non branché"):
        BeirLoader("nfcorpus")


def test_full_test_split(loader: BeirLoader) -> None:
    ds = loader.load("test")
    # 3 requêtes jugées en test ; q13 (train) et q99 (jamais jugée) sont écartées.
    assert sorted(q.query_id for q in ds.queries) == ["1", "3", "5"]
    # Corpus complet en mode non échantillonné, distracteur compris.
    assert len(ds.documents) == 6
    assert ds.sampled is False
    # Les ids qrels, entiers côté source, sont normalisés en str.
    assert ds.relevant_doc_ids("1") == {"4983", "5836"}


def test_train_split_is_disjoint(loader: BeirLoader) -> None:
    ds = loader.load("train")
    assert [q.query_id for q in ds.queries] == ["13"]
    assert ds.relevant_doc_ids("13") == {"7912"}


def test_sampling_truncates_and_flags(loader: BeirLoader) -> None:
    ds = loader.load("test", max_queries=2)
    assert ds.sampled is True
    # Ordre du fichier queries, donc déterministe.
    assert [q.query_id for q in ds.queries] == ["1", "3"]
    # Le corpus échantillonné ne garde que les documents jugés par les requêtes retenues.
    assert sorted(d.doc_id for d in ds.documents) == ["19238", "4983", "5836"]
    assert "5" not in ds.qrels


def test_sampling_larger_than_split_is_a_no_op(loader: BeirLoader) -> None:
    ds = loader.load("test", max_queries=50)
    assert ds.sampled is False
    assert len(ds.documents) == 6


def test_missing_fixture_split_raises(loader: BeirLoader) -> None:
    with pytest.raises(FileNotFoundError, match="qrels_dev"):
        loader.load("dev")


@pytest.mark.network
def test_real_scifact_test_split(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Smoke test contre le vrai dépôt HF — lancé à la main via `make test-network`."""
    settings = Settings(data_dir=tmp_path_factory.mktemp("hf-cache"))
    ds = BeirLoader("scifact", settings=settings).load("test")
    assert len(ds.documents) == 5183
    assert len(ds.queries) == 300
    assert ds.sampled is False
