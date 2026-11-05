"""Suite configuration and the arms that need no database."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from llm_testbench.config import Settings
from llm_testbench.eval.suite import ArmConfig, SuiteConfig, Suites, load_dataset, run_arm
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.registry import Registry

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def suites() -> Suites:
    return Suites.load(REPO_ROOT / "config" / "eval_suites.toml")


def dense(**overrides: object) -> ArmConfig:
    values: dict[str, object] = {
        "name": "arm",
        "dataset": "beir/scifact",
        "retriever": "dense",
        "embedding_model": "hf/BAAI/bge-base-en-v1.5",
    }
    values.update(overrides)
    return ArmConfig.model_validate(values)


def test_the_versioned_suites_are_valid_and_buildable(suites: Suites) -> None:
    """Every dense arm names an enabled backend and a model whose vector size is declared:
    a typo in the suite file fails here, not after ten minutes of embedding."""
    registry = Registry.load(REPO_ROOT / "config" / "llm_backends.toml")
    baseline = suites.get("retrieval-baseline")
    assert {arm.dataset for arm in baseline.arms} == {"beir/scifact", "beir/nfcorpus", "beir/fiqa"}
    for arm in baseline.arms:
        if arm.retriever == "dense":
            assert arm.embedding_model is not None
            registry.resolve(arm.embedding_model)
            assert registry.embedding_dimensions(arm.embedding_model) is not None
        index_key, _ = arm.keys() if arm.retriever == "dense" else ("ok", "")
        assert len(index_key) <= 63


def test_the_baseline_arms_read_the_index_the_api_serves(suites: Suites) -> None:
    ((arm,), _) = suites.get("retrieval-baseline").select(["scifact-oai-chunks-hnsw"])
    defaults = Settings()
    assert arm.keys() == (defaults.index_key, defaults.source_key)
    assert (arm.chunk_size, arm.chunk_overlap) == (1_000, 200)


def test_index_and_source_keys_are_derived_from_the_arm() -> None:
    assert dense(chunk_size=0).keys() == (
        "scifact-whole-bge-base-en-v1-5",
        "docs:scifact:whole",
    )
    # The phase 1 cut keeps the phase 1 source: its chunks are shared by every model.
    assert dense().keys() == ("scifact-r1000-200-bge-base-en-v1-5", "docs:scifact")
    assert dense(chunk_size=400, chunk_overlap=0).keys()[1] == "docs:scifact:r400-0"
    assert dense(chunk_size=0).chunker().describe()["chunk_overlap"] == 0


def test_sample_keys_never_collide_with_real_indexes() -> None:
    pinned = dense(index_key="scifact-recursive-oai-small", source_key="docs:scifact")
    assert pinned.keys() == ("scifact-recursive-oai-small", "docs:scifact")
    index_key, source_key = pinned.keys(sample=True)
    assert index_key.startswith("sample-")
    assert source_key.startswith("sample:")


def test_invalid_arms_are_refused() -> None:
    with pytest.raises(ValidationError, match="needs embedding_model"):
        ArmConfig(name="arm", dataset="beir/scifact", retriever="dense")
    with pytest.raises(ValidationError, match="together"):
        dense(index_key="only-one")
    with pytest.raises(ValidationError):
        dense(chunk_sise=10)  # a typo in the suite file is an error, not a silent default
    arm = ArmConfig(name="arm", dataset="beir/scifact", retriever="bm25")
    with pytest.raises(ValidationError, match="share a name"):
        SuiteConfig(arms=(arm, arm))


def test_unknown_suite_arm_and_dataset(suites: Suites, offline_settings: Settings) -> None:
    with pytest.raises(KeyError, match="unknown suite"):
        suites.get("nope")
    with pytest.raises(KeyError, match="unknown arm"):
        suites.get("retrieval-baseline").select(["nope"])
    arm = ArmConfig(name="arm", dataset="beir/trec-covid", retriever="bm25")
    with pytest.raises(ValueError, match="no loader"):
        load_dataset(arm, offline_settings)


async def test_bm25_arm_runs_offline_on_fixtures(offline_settings: Settings) -> None:
    arm = ArmConfig(name="scifact-bm25", dataset="beir/scifact", retriever="bm25")
    suite = SuiteConfig(arms=(arm,))
    run = await run_arm(
        "unit",
        suite,
        arm,
        settings=offline_settings,
        client=LLMClient.from_settings(offline_settings),
        store=None,
    )
    # Three fixture queries, each worded like the document judged relevant for it.
    assert run.metrics["mrr_at_10"].mean > 0.5
    assert run.index is not None
    assert run.index.documents == 6
    assert run.retriever["retriever"] == "bm25"
    # Read from fixtures: the three queries are the whole "split", and still not a number.
    assert run.dataset["sampled"] is False
    assert not run.publishable


async def test_a_dense_arm_without_a_database_is_refused(offline_settings: Settings) -> None:
    arm = dense()
    with pytest.raises(ValueError, match="database is required"):
        await run_arm(
            "unit",
            SuiteConfig(arms=(arm,)),
            arm,
            settings=offline_settings,
            client=LLMClient.from_settings(offline_settings),
            store=None,
        )


def test_nfcorpus_fixture_has_graded_judgments(offline_settings: Settings) -> None:
    arm = ArmConfig(name="arm", dataset="beir/nfcorpus", retriever="bm25")
    dataset = load_dataset(arm, offline_settings)
    assert dataset.qrels["PLAIN-2"] == {"MED-10": 2, "MED-14": 1}
    assert [query.query_id for query in dataset.queries] == ["PLAIN-2", "PLAIN-12"]
    documents = dataset.parsed_documents()
    assert documents[0].title == "Statin use and breast cancer survival"
    assert documents[0].source_uri == "hf:BeIR/nfcorpus/MED-10"
    assert documents[0].metadata == {"dataset": "nfcorpus"}
