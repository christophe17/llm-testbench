from llm_testbench.llm.governance import DataClass
from llm_testbench.sources import Capability, Citation, Evidence, Provenance, SearchQuery


def test_citation_label_is_homogeneous_across_sources() -> None:
    doc = Provenance(
        source_key="docs:scifact",
        document_id="4983",
        chunk_id="4983#0002",
        locator="section « Results », caractères 10–120",
        title="A paper",
    )
    sql = Provenance(source_key="sql:spider", document_id="query-7", locator="lignes 1–3")
    evidence = Evidence(text="…", score=0.9, rank=1, provenance=doc)
    assert Citation.from_evidence(1, evidence).render() == (
        "[1] docs:scifact › A paper › section « Results », caractères 10–120"
    )
    assert sql.label() == "sql:spider › query-7 › lignes 1–3"


def test_search_query_requires_a_data_class_and_bounds_k() -> None:
    query = SearchQuery(text="q", data_class=DataClass.PUBLIC)
    assert query.k == 5
    assert Capability.SEARCH.value == "search"
