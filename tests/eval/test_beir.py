from collections.abc import Callable
from typing import Any

import pytest

from llm_testbench.eval.loaders.beir import build_retrieval_dataset, load_beir


def test_build_filters_unjudged_queries(fixture_json: Callable[[str], Any]) -> None:
    raw = fixture_json("beir.json")
    ds = build_retrieval_dataset("scifact", raw["corpus"], raw["queries"], raw["qrels"])

    assert ds.name == "beir/scifact"
    assert len(ds.documents) == 3
    # q3 n'a aucun jugement : elle doit disparaître, sinon elle plombe les métriques.
    assert [q.query_id for q in ds.queries] == ["q1", "q2"]


def test_qrels_are_graded(fixture_json: Callable[[str], Any]) -> None:
    raw = fixture_json("beir.json")
    ds = build_retrieval_dataset("scifact", raw["corpus"], raw["queries"], raw["qrels"])

    assert ds.qrels["q1"] == {"d1": 1, "d2": 2}
    assert ds.qrels["q2"] == {"d3": 1}


def test_null_title_becomes_empty_string(fixture_json: Callable[[str], Any]) -> None:
    raw = fixture_json("beir.json")
    ds = build_retrieval_dataset("scifact", raw["corpus"], raw["queries"], raw["qrels"])

    d2 = next(d for d in ds.documents if d.doc_id == "d2")
    assert d2.title == ""


def test_unknown_dataset_is_rejected() -> None:
    with pytest.raises(ValueError, match="non retenu"):
        load_beir("msmarco")
