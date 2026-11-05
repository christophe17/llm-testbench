from itertools import pairwise

from llm_testbench.config import Settings
from llm_testbench.eval.loaders.hotpotqa import HotpotQALoader
from llm_testbench.llm.testing import HashingEmbedder
from llm_testbench.retrieval import BM25Retriever


def test_the_pool_is_one_corpus_with_two_gold_paragraphs_per_question(
    offline_settings: Settings,
) -> None:
    dataset = HotpotQALoader(offline_settings).load_retrieval(pool=1_000)
    # Three questions kept (the fourth names a gold paragraph its context does not hold);
    # "Analytical Engine" appears in two contexts and once in the corpus of nine
    # paragraphs, the empty stub nowhere.
    assert dataset.describe() == {
        "dataset": "hotpotqa/pool-1000",
        "split": "validation",
        "documents": 9,
        "queries": 3,
        "judgments": 6,
        "sampled": False,
    }
    assert dataset.qrels["h-river"] == {"Avignon": 1, "Rhone": 1}
    assert dataset.document_by_id("Rhone").text == (
        "The Rhone is a major river in France and Switzerland. "
        "It empties into the Mediterranean Sea."
    )


def test_a_question_carries_its_gold_paragraphs_and_the_corpus(
    offline_settings: Settings,
) -> None:
    dataset = HotpotQALoader(offline_settings).load()
    example = dataset.examples[0]
    assert (example.example_id, example.kind, example.answers) == (
        "h-nationality",
        "comparison",
        ("yes",),
    )
    assert [passage.document_id for passage in example.passages] == [
        "Ada Lovelace",
        "Charles Babbage",
    ]
    assert example.scope == {}
    assert dataset.describe()["corpus_documents"] == 9
    assert {document.doc_id for document in dataset.corpus} >= {"Ada Lovelace", "Radium"}


def test_a_subsample_keeps_the_whole_pool_as_corpus(offline_settings: Settings) -> None:
    loader = HotpotQALoader(offline_settings)
    drawn = loader.load(max_examples=2, seed=3)
    assert len(drawn.examples) == 2
    assert drawn.subsample_seed == 3
    assert len(drawn.corpus) == 9
    assert loader.load(max_examples=2, seed=3) == drawn


async def test_the_fixture_has_no_tie_where_a_metric_is_decided(
    offline_settings: Settings,
) -> None:
    """The gate compares sample-mode scores between machines. A fixture where two
    paragraphs score the same at a rank that counts makes those scores depend on the
    machine: this test fails first, with the question to reword."""
    dataset = HotpotQALoader(offline_settings).load_retrieval()
    lexical = BM25Retriever(dataset.documents)
    embedder = HashingEmbedder(256)
    vectors = {
        document.doc_id: embedder.vector(f"{document.title} {document.text}")
        for document in dataset.documents
    }
    for query in dataset.queries:
        scores = [hit.score for hit in (await lexical.retrieve(query.text, k=10)).documents]
        assert len(set(scores)) == len(scores), f"{query.query_id}: BM25 tie in {scores}"
        asked = embedder.vector(query.text)
        cosines = sorted(
            (sum(a * b for a, b in zip(asked, vector, strict=True)) for vector in vectors.values()),
            reverse=True,
        )
        # The end-to-end arm of the gate keeps two chunks: ranks 1 to 3 must be apart.
        gaps = [first - second for first, second in pairwise(cosines[:3])]
        assert min(gaps) > 1e-6, f"{query.query_id}: tie among the nearest vectors {cosines[:3]}"
