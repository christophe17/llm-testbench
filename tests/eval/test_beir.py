import pytest

from llm_testbench.config import Settings
from llm_testbench.eval.loaders import BeirLoader
from llm_testbench.retrieval import BM25Retriever


@pytest.fixture
def loader(offline_settings: Settings) -> BeirLoader:
    return BeirLoader("scifact", settings=offline_settings)


def test_unknown_beir_dataset_rejected() -> None:
    with pytest.raises(ValueError, match="not wired"):
        BeirLoader("trec-covid")


def test_full_test_split(loader: BeirLoader) -> None:
    ds = loader.load("test")
    # 3 queries judged in test; q13 (train) and q99 (never judged) are dropped.
    assert sorted(q.query_id for q in ds.queries) == ["1", "3", "5"]
    # Full corpus in non-sampled mode, distractor included.
    assert len(ds.documents) == 6
    assert ds.sampled is False
    # The qrels ids, integers on the source side, are normalized to str.
    assert ds.relevant_doc_ids("1") == {"4983", "5836"}


def test_train_split_is_disjoint(loader: BeirLoader) -> None:
    ds = loader.load("train")
    assert [q.query_id for q in ds.queries] == ["13"]
    assert ds.relevant_doc_ids("13") == {"7912"}


def test_sampling_truncates_and_flags(loader: BeirLoader) -> None:
    ds = loader.load("test", max_queries=2)
    assert ds.sampled is True
    # Order of the queries file, hence deterministic.
    assert [q.query_id for q in ds.queries] == ["1", "3"]
    # The sampled corpus keeps only the documents judged by the retained queries.
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
    """Smoke test against the real HF repository — run by hand via `make test-network`."""
    settings = Settings(data_dir=tmp_path_factory.mktemp("hf-cache"))
    ds = BeirLoader("scifact", settings=settings).load("test")
    assert len(ds.documents) == 5183
    assert len(ds.queries) == 300
    assert ds.sampled is False


@pytest.mark.parametrize("name", ["scifact", "nfcorpus"])
async def test_the_fixtures_have_no_lexical_tie(name: str, offline_settings: Settings) -> None:
    """Same guard as for the HotpotQA fixture: two documents with the same BM25 score and
    different judgments make a sample-mode score depend on how ties are ordered."""
    dataset = BeirLoader(name, settings=offline_settings).load("test")
    lexical = BM25Retriever(dataset.documents)
    for query in dataset.queries:
        scores = [hit.score for hit in (await lexical.retrieve(query.text, k=10)).documents]
        assert len(set(scores)) == len(scores), f"{name} query {query.query_id}: tie in {scores}"
