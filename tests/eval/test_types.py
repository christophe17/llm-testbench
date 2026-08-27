import pytest
from pydantic import ValidationError

from llm_testbench.eval.types import DatasetInfo, Document, Query, RetrievalDataset

INFO = DatasetInfo(
    key="test/mini",
    name="Mini",
    homepage="https://example.org",
    license="cc0",
    source="fixtures",
)


def make_dataset(**overrides: object) -> RetrievalDataset:
    fields: dict[str, object] = {
        "info": INFO,
        "split": "test",
        "documents": (Document(doc_id="d1", text="un"), Document(doc_id="d2", text="deux")),
        "queries": (Query(query_id="q1", text="quoi ?"),),
        "qrels": {"q1": {"d1": 2, "d2": 0}},
    }
    fields.update(overrides)
    return RetrievalDataset(**fields)  # type: ignore[arg-type]


def test_valid_dataset_builds() -> None:
    ds = make_dataset()
    assert ds.describe() == {
        "dataset": "test/mini",
        "split": "test",
        "documents": 2,
        "queries": 1,
        "judgments": 2,
        "sampled": False,
    }


def test_qrels_referencing_unknown_document_rejected() -> None:
    with pytest.raises(ValidationError, match="documents absents"):
        make_dataset(qrels={"q1": {"d1": 1, "ghost": 1}})


def test_qrels_referencing_unknown_query_rejected() -> None:
    with pytest.raises(ValidationError, match="requêtes absentes"):
        make_dataset(qrels={"q1": {"d1": 1}, "ghost": {"d2": 1}})


def test_query_without_any_judgment_rejected() -> None:
    with pytest.raises(ValidationError, match="sans aucun jugement"):
        make_dataset(queries=(Query(query_id="q1", text="a"), Query(query_id="q2", text="b")))


def test_duplicate_doc_id_rejected() -> None:
    with pytest.raises(ValidationError, match="doc_id en double"):
        make_dataset(
            documents=(Document(doc_id="d1", text="un"), Document(doc_id="d1", text="bis"))
        )


def test_relevant_doc_ids_honours_min_relevance() -> None:
    ds = make_dataset()
    assert ds.relevant_doc_ids("q1") == {"d1"}  # d2 est jugé non pertinent (score 0)
    assert ds.relevant_doc_ids("q1", min_relevance=2) == {"d1"}
    assert ds.relevant_doc_ids("q1", min_relevance=3) == set()
    assert ds.relevant_doc_ids("inconnue") == set()


def test_document_by_id() -> None:
    ds = make_dataset()
    assert ds.document_by_id("d2").text == "deux"
    with pytest.raises(KeyError, match="ghost"):
        ds.document_by_id("ghost")
