import pytest

from llm_testbench.config import Settings
from llm_testbench.eval.loaders import BeirLoader
from llm_testbench.eval.types import Document
from llm_testbench.retrieval import BM25Retriever, Retriever


@pytest.fixture
def retriever(offline_settings: Settings) -> BM25Retriever:
    return BM25Retriever(BeirLoader("scifact", settings=offline_settings).load("test").documents)


async def test_the_document_sharing_the_query_words_comes_first(retriever: BM25Retriever) -> None:
    retrieval = await retriever.retrieve("Statins increase the rate of myalgia.", k=3)
    assert retrieval.doc_ids[0] == "13734"
    assert [document.rank for document in retrieval.documents] == list(
        range(1, len(retrieval.documents) + 1)
    )
    scores = [document.score for document in retrieval.documents]
    assert scores == sorted(scores, reverse=True)
    assert retrieval.cost_usd == 0.0
    assert set(retrieval.timings_ms) == {"search"}


async def test_stemming_matches_inflected_forms() -> None:
    documents = [
        Document(doc_id="a", title="", text="Mitochondria regulate innate immunity."),
        Document(doc_id="b", title="", text="A recipe with flour and eggs."),
    ]
    retrieval = await BM25Retriever(documents).retrieve("immune regulation by mitochondrion", k=2)
    # "regulate"/"regulation" share a stem; "mitochondrion"/"mitochondria" do not (Snowball
    # is rule-based, it knows no Latin plural): one matching word is enough to retrieve.
    assert retrieval.doc_ids == ["a"]


async def test_the_title_is_indexed_with_the_text() -> None:
    documents = [
        Document(doc_id="a", title="Zebrafish", text="A study of regeneration."),
        Document(doc_id="b", title="Mouse", text="A study of regeneration."),
    ]
    assert (await BM25Retriever(documents).retrieve("zebrafish", k=2)).doc_ids == ["a"]


async def test_a_query_sharing_no_word_retrieves_nothing(retriever: BM25Retriever) -> None:
    # Unknown words, then stop words only: bm25s would fill the list with zero scores.
    assert (await retriever.retrieve("zzzz qqqq", k=5)).documents == ()
    assert (await retriever.retrieve("the of and", k=5)).documents == ()


async def test_k_larger_than_the_corpus(retriever: BM25Retriever) -> None:
    retrieval = await retriever.retrieve("RNA translation statin mitochondria brain", k=100)
    assert 1 <= len(retrieval.documents) <= 6
    assert len(set(retrieval.doc_ids)) == len(retrieval.doc_ids)


def test_describe_and_protocol(retriever: BM25Retriever) -> None:
    assert isinstance(retriever, Retriever)
    description = retriever.describe()
    assert description["retriever"] == "bm25"
    assert description["documents"] == 6
    assert (description["k1"], description["b"], description["method"]) == (1.5, 0.75, "lucene")


def test_an_empty_corpus_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one document"):
        BM25Retriever([])
