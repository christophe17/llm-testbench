from llm_testbench.config import Settings
from llm_testbench.eval.loaders.hotpotqa import HotpotQALoader


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
