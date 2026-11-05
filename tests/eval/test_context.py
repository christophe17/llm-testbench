"""Gold or retrieved context, and the rule that says a gold passage was found."""

import pytest

from llm_testbench.config import Settings
from llm_testbench.eval.context import (
    GoldContext,
    NoContext,
    RetrievedContext,
    passage_found,
    score_context,
)
from llm_testbench.eval.loaders.hotpotqa import HotpotQALoader
from llm_testbench.eval.loaders.qasper import QasperLoader
from llm_testbench.eval.qa import Passage
from llm_testbench.llm.embeddings import EmbeddingResult
from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.types import ModelRef, Usage
from llm_testbench.sources.types import Evidence, Provenance

PARAGRAPH = (
    "We compare our approach with pivoting and with multilingual translation. "
    "The results show that it outperforms both across languages and datasets."
)


def chunk(text: str, document_id: str = "paper-1") -> Evidence:
    return Evidence(
        text=text,
        score=0.5,
        rank=1,
        provenance=Provenance(source_key="docs:unit", document_id=document_id, locator="chunk"),
    )


def gold(text: str = PARAGRAPH, document_id: str | None = "paper-1") -> Passage:
    return Passage(passage_id="p1", text=text, document_id=document_id)


def test_a_passage_inside_a_chunk_is_found_whatever_the_whitespace() -> None:
    cut = chunk("Earlier sentence.\n\n" + PARAGRAPH.replace(". ", ".\n") + " Later sentence.")
    assert passage_found(gold(), (cut,))


def test_a_passage_cut_by_the_chunker_is_found_when_one_chunk_holds_half_of_it() -> None:
    middle = len(PARAGRAPH) // 2
    most = chunk(PARAGRAPH[: middle + 20])
    little = chunk(PARAGRAPH[-30:])
    assert passage_found(gold(), (most,))
    # Two small pieces do not add up: no single chunk holds half of the passage.
    assert not passage_found(gold(), (little, chunk(PARAGRAPH[:30])))


def test_the_same_words_in_another_document_do_not_count() -> None:
    assert not passage_found(gold(), (chunk(PARAGRAPH, document_id="paper-2"),))
    # A dataset without a corpus names no document: the text alone decides.
    assert passage_found(gold(document_id=None), (chunk(PARAGRAPH, document_id="paper-2"),))


def test_a_multi_hop_question_is_complete_only_with_both_paragraphs(
    offline_settings: Settings,
) -> None:
    example = HotpotQALoader(offline_settings).load().examples[0]
    first, second = example.passages
    one = (chunk(first.text, document_id=first.passage_id),)
    assert score_context(example, one) == {
        "context_empty": 0.0,
        "context_recall": 0.5,
        "context_complete": 0.0,
    }
    both = (*one, chunk(second.text, document_id=second.passage_id))
    assert score_context(example, both)["context_complete"] == 1.0
    assert score_context(example, ()) == {
        "context_empty": 1.0,
        "context_recall": 0.0,
        "context_complete": 0.0,
    }


def test_an_unanswerable_question_has_no_passage_to_find(offline_settings: Settings) -> None:
    examples = {e.example_id: e for e in QasperLoader(offline_settings).load_qa().examples}
    assert score_context(examples["q4"], (chunk("Anything."),)) == {"context_empty": 0.0}


async def test_gold_context_is_the_passages_as_numbered_evidence(
    offline_settings: Settings,
) -> None:
    example = HotpotQALoader(offline_settings).load().examples[0]
    provider = GoldContext("hotpotqa")
    given = await provider.context(example)
    assert [item.provenance.document_id for item in given.evidence] == [
        "Ada Lovelace",
        "Charles Babbage",
    ]
    assert (given.cost_usd, provider.retrieved) == (0.0, False)
    assert provider.describe() == {"context": "gold passages"}


async def test_closed_book_hands_over_nothing_and_asks_every_question(
    offline_settings: Settings,
) -> None:
    examples = {e.example_id: e for e in QasperLoader(offline_settings).load_qa().examples}
    closed = NoContext()
    assert (await closed.context(examples["q1"])).evidence == ()
    # The gold context has nothing to ask the unanswerable QASPER question on; the closed
    # book and the search ask it like the others.
    assert closed.applies_to(examples["q4"])
    assert not GoldContext("qasper").applies_to(examples["q4"])
    assert closed.describe() == {"context": "none (closed book)"}


class FakeSource:
    """The two halves of ``DocumentSource.search``, recording what they were asked."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    class spec:
        index_key = "unit-index"
        embedding_model = ModelRef.parse("openai/text-embedding-3-small")

    async def embed_query(self, text: str, data_class: DataClass) -> EmbeddingResult:
        return EmbeddingResult(
            model="text-embedding-3-small",
            backend="openai",
            vectors=((0.1, 0.2),),
            usage=Usage(input_tokens=7),
            cost_usd=0.000001,
            latency_ms=3.0,
        )

    async def search_vector(self, vector: object, **options: object) -> list[Evidence]:
        self.calls.append(options)
        return [chunk("Retrieved text.")]


async def test_retrieved_context_searches_inside_the_scope_and_keeps_the_cost(
    offline_settings: Settings,
) -> None:
    examples = {e.example_id: e for e in QasperLoader(offline_settings).load_qa().examples}
    source = FakeSource()
    provider = RetrievedContext(source, k=3)  # type: ignore[arg-type]
    given = await provider.context(examples["q3"])
    assert source.calls == [{"k": 3, "filters": {"paper_id": "1001.0002"}}]
    assert given.cost_usd == pytest.approx(0.000001)
    assert given.latency_ms > 0
    assert provider.describe() == {
        "context": "retrieved",
        "k": 3,
        "index_key": "unit-index",
        "embedding_model": "openai/text-embedding-3-small",
    }
