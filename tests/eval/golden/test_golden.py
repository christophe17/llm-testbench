"""The golden set offline: drafting on a scripted model, review, freeze, closed-book probe."""

import datetime as dt
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from llm_testbench.config import Settings
from llm_testbench.eval.corpus.arxiv import CC_BY_4, HTML_URL, PDF_URL, ArxivClient
from llm_testbench.eval.corpus.build import Corpus, build_corpus
from llm_testbench.eval.corpus.manifest import CorpusConfig
from llm_testbench.eval.corpus.reference import reference_document
from llm_testbench.eval.golden.cli import probe_all, status
from llm_testbench.eval.golden.dataset import golden_dataset
from llm_testbench.eval.golden.drafting import (
    Drafter,
    UnanswerableChecker,
    assign_categories,
    locate,
    paper_text,
    pick_documents,
)
from llm_testbench.eval.golden.review import review, show
from llm_testbench.eval.golden.store import (
    CHANGELOG,
    freeze,
    read_drafts,
    read_questions,
    read_reviews,
    write_drafts,
)
from llm_testbench.eval.golden.types import Category, Draft, Quote, Review, apply_review
from llm_testbench.generation.answer import REFUSAL_SENTINEL
from llm_testbench.ingest.parsing import ParsedDocument
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.prompts import PromptRegistry
from llm_testbench.llm.types import ModelRef
from tests.conftest import FIXTURES_DIR
from tests.ingest.test_pdf import tiny_pdf
from tests.llm.fakes import FakeProvider, make_completion

DRAFTER = ModelRef.parse("openai/gpt-5.6-terra")
GENERATOR = ModelRef.parse("anthropic/claude-sonnet-5-5")
PAPER = (FIXTURES_DIR / "arxiv" / "2610.00001v1.html").read_text(encoding="utf-8")

MODEL_REPLY = {
    "questions": [
        {
            "category": "factual",
            "question": "What recall at 10 does the dense retriever reach on the new corpus?",
            "answer": "0.74",
            "quotes": ["Dense | 0.74"],
            "note": "",
        },
        {
            "category": "multi_hop",
            "question": "How much slower is the retriever with the higher recall?",
            "answer": "The dense retriever, 31 ms against 2 ms.",
            # The second quote is a paraphrase: the paper does not contain this sentence.
            "quotes": ["Dense | 0.74", "The dense retriever takes 31 milliseconds."],
            "note": "",
        },
        {
            "category": "unanswerable",
            "question": "Which GPU was the dense index built on?",
            "answer": "An A100.",
            "quotes": ["Measured on one machine."],
            "note": "The hardware is never named.",
        },
        # Not requested, repeated, or empty: all three are dropped.
        {
            "category": "trap",
            "question": "Does BM25 win?",
            "answer": "No.",
            "quotes": [],
            "note": "",
        },
        {
            "category": "factual",
            "question": "A second one?",
            "answer": "x",
            "quotes": [],
            "note": "",
        },
        {"category": "temporal", "question": "", "answer": "", "quotes": [], "note": ""},
    ]
}


@pytest.fixture
def document() -> ParsedDocument:
    parsed, _ = reference_document(PAPER, "2610.00001v1", title="A Fresh Paper With Tables")
    return parsed


def client_with(settings: Settings, backend: str, model: str, texts: list[str]) -> LLMClient:
    client = LLMClient.from_settings(settings)
    script = [
        make_completion(text, model=model, backend=backend, input_tokens=5000, output_tokens=600)
        for text in texts
    ]
    client.register_provider(backend, FakeProvider(backend, script=script))
    return client


async def drafts_of(settings: Settings, document: ParsedDocument) -> list[Draft]:
    drafter = Drafter(
        client=client_with(settings, "openai", "gpt-5.6-terra", [json.dumps(MODEL_REPLY)]),
        prompts=PromptRegistry.from_settings(settings),
        model=DRAFTER,
    )
    kinds = (Category.FACTUAL, Category.MULTI_HOP, Category.UNANSWERABLE, Category.TEMPORAL)
    return await drafter.draft(document, kinds)


def test_a_quote_is_evidence_only_word_for_word(document: ParsedDocument) -> None:
    found = locate("Dense retrieval beats   BM25 when k=10.", document)
    assert (found.found, found.section) == (True, "1 Introduction")
    row = locate("Dense | 0.74", document)
    assert (row.found, row.section) == (True, "2 Results")
    paraphrase = locate("Dense retrieval is better than BM25 at k=10.", document)
    assert (paraphrase.found, paraphrase.section) == (False, "")


def test_the_drafter_reads_the_paper_in_order_up_to_a_budget(document: ParsedDocument) -> None:
    whole = paper_text(document, 10_000)
    assert whole.startswith("TITLE: A Fresh Paper With Tables\n\n## Abstract\n")
    assert "## 2.1 Cost" in whole
    cut = paper_text(document, 200)
    assert "## 1 Introduction" in cut
    assert "## 2 Results" not in cut


def test_kinds_rotate_and_documents_are_drawn_with_a_seed() -> None:
    plan = assign_categories(4, 3)
    assert plan[0] == (Category.FACTUAL, Category.MULTI_HOP, Category.UNANSWERABLE)
    assert plan[1] == (Category.AMBIGUOUS, Category.TRAP, Category.TEMPORAL)
    assert plan[2] == plan[0]
    ids = [f"d{number}" for number in range(10)]
    assert pick_documents(ids, 3, seed=0) == pick_documents(ids, 3, seed=0)
    assert len(pick_documents(ids, 3, seed=0)) == 3
    assert pick_documents(ids, 50, seed=0) == ids


async def test_drafts_keep_one_question_per_requested_kind_and_check_their_quotes(
    offline_settings: Settings, document: ParsedDocument
) -> None:
    drafts = await drafts_of(offline_settings, document)
    assert [draft.category for draft in drafts] == [
        Category.FACTUAL,
        Category.MULTI_HOP,
        Category.UNANSWERABLE,
    ]
    factual, multi_hop, unanswerable = drafts
    assert factual.draft_id == "2610.00001v1-factual"
    assert factual.drafted_by == "openai/gpt-5.6-terra"
    assert factual.problems() == []
    assert [quote.found for quote in multi_hop.quotes] == [True, False]
    assert multi_hop.problems() == [
        "1 quote(s) not found in the document",
        "multi-hop, but the quotes found come from fewer than two sections",
    ]
    # An unanswerable question has neither an answer nor evidence, whatever the model wrote.
    assert (unanswerable.answer, unanswerable.quotes) == ("", ())
    assert unanswerable.note == "The hardware is never named."


async def test_review_is_resumable_and_the_last_decision_wins(
    offline_settings: Settings, document: ParsedDocument, tmp_path: Path
) -> None:
    drafts = await drafts_of(offline_settings, document)
    write_drafts(drafts, tmp_path)
    assert read_drafts(tmp_path) == drafts
    shown: list[str] = []
    # Accept the first, then stop.
    keys = iter(["?", "a", "q"])
    assert review(drafts, tmp_path, read=lambda _prompt: next(keys), write=shown.append) == 1
    assert any("Accept when" in line for line in shown)
    assert any("NOT FOUND in the document" in line for line in shown)
    # Resume: the first draft is not shown again. Edit the second, reject the third.
    keys = iter(
        [
            "e",
            "How many milliseconds does the dense retriever take?",
            "31 ms",
            "factual",
            "r",
            "guessable",
        ]
    )
    shown.clear()
    assert review(drafts, tmp_path, read=lambda _prompt: next(keys), write=shown.append) == 2
    assert "1 of 3 drafts already reviewed, 2 to go.\n" in shown
    reviews = read_reviews(tmp_path)
    assert [reviews[draft.draft_id].decision for draft in drafts] == [
        "accepted",
        "edited",
        "rejected",
    ]
    assert reviews[drafts[1].draft_id].category is Category.FACTUAL
    # A second look overrules the first decision.
    keys = iter(["r", ""])
    assert (
        review(drafts[:1], tmp_path, again=True, read=lambda _p: next(keys), write=shown.append)
        == 1
    )
    assert read_reviews(tmp_path)[drafts[0].draft_id].decision == "rejected"


async def test_freeze_writes_the_set_and_its_changelog(
    offline_settings: Settings, document: ParsedDocument, tmp_path: Path
) -> None:
    drafts = await drafts_of(offline_settings, document)
    write_drafts(drafts, tmp_path)
    keys = iter(["a", "e", "", "31 ms against 2 ms", "", "a"])
    review(drafts, tmp_path, read=lambda _prompt: next(keys), write=lambda _line: None)
    questions = freeze(tmp_path, version="v1", summary="First review.", today=dt.date(2026, 11, 6))
    assert read_questions(tmp_path) == questions
    assert [question.question_id for question in questions] == [
        "g-2610.00001v1-factual",
        "g-2610.00001v1-multi_hop",
        "g-2610.00001v1-unanswerable",
    ]
    edited, unanswerable = questions[1], questions[2]
    assert (edited.answer, edited.edited) == ("31 ms against 2 ms", True)
    assert (unanswerable.answerable, unanswerable.answer) == (False, "")
    log = (tmp_path / CHANGELOG).read_text(encoding="utf-8")
    assert "## v1 — 2026-11-06" in log
    assert (
        "3 questions: 1 factual, 1 multi_hop, 1 unanswerable, 0 ambiguous, 0 trap, 0 temporal."
        in log
    )
    assert "3 added, 0 removed, 0 changed" in log
    with pytest.raises(ValueError, match="already in the changelog"):
        freeze(tmp_path, version="v1", summary="Again.")
    # A later review rejects one question: the next version says what moved.
    keys = iter(["r", "wrong answer"])
    review(drafts[:1], tmp_path, again=True, read=lambda _p: next(keys), write=lambda _l: None)
    second = freeze(tmp_path, version="v2", summary="One removed.", today=dt.date(2026, 11, 7))
    assert len(second) == 2
    log = (tmp_path / CHANGELOG).read_text(encoding="utf-8")
    assert log.index("## v2") < log.index("## v1")
    assert "0 added, 1 removed, 0 changed" in log
    assert "frozen set: 2" in status(tmp_path)


def test_a_review_says_what_it_changed() -> None:
    now = dt.datetime(2026, 11, 6, tzinfo=dt.UTC)
    with pytest.raises(ValidationError, match="nothing was changed"):
        Review(draft_id="d", decision="edited", reviewed_at=now)
    with pytest.raises(ValidationError, match="needs the decision 'edited'"):
        Review(draft_id="d", decision="accepted", answer="x", reviewed_at=now)
    draft = Draft(
        draft_id="d",
        doc_id="p",
        category=Category.FACTUAL,
        question="Q?",
        answer="A",
        quotes=(Quote(doc_id="p", text="A.", section="1", found=True),),
        drafted_by="m",
        prompt_version="1",
    )
    moved = apply_review(
        draft,
        Review(draft_id="d", decision="edited", category=Category.UNANSWERABLE, reviewed_at=now),
        "g-d",
    )
    assert moved is not None
    assert (moved.answerable, moved.answer, moved.edited) == (False, "", True)
    with pytest.raises(ValueError, match="applied to"):
        apply_review(draft, Review(draft_id="x", decision="accepted", reviewed_at=now), "g")


async def test_closed_book_probe_flags_a_question_that_can_be_guessed(
    offline_settings: Settings, document: ParsedDocument
) -> None:
    drafts = await drafts_of(offline_settings, document)
    replies = ["It reaches 0.74.", REFUSAL_SENTINEL, REFUSAL_SENTINEL]
    probed = await probe_all(
        drafts,
        client=client_with(offline_settings, "anthropic", "claude-sonnet-5-5", replies),
        prompts=PromptRegistry.from_settings(offline_settings),
        model=GENERATOR,
        ledger=None,
    )
    assert [draft.closed_book_correct for draft in probed] == [True, False, False]
    assert "answered correctly without any document: guessable" in probed[0].problems()
    assert probed[1].closed_book_answer == REFUSAL_SENTINEL


async def test_a_question_without_verbatim_evidence_cannot_be_accepted(
    offline_settings: Settings, document: ParsedDocument, tmp_path: Path
) -> None:
    drafts = await drafts_of(offline_settings, document)
    paraphrased = drafts[1].model_copy(
        update={"quotes": tuple(quote for quote in drafts[1].quotes if not quote.found)}
    )
    shown: list[str] = []
    # Accept is refused and asked again; an edit that keeps it answerable is refused too;
    # turning it into an unanswerable question is a way out.
    keys = iter(["a", "e", "", "", "", "e", "", "", "unanswerable"])
    recorded = review(
        [paraphrased, paraphrased], tmp_path, read=lambda _p: next(keys), write=shown.append
    )
    assert recorded == 1
    assert sum("None of its quotes is in the document" in line for line in shown) == 2
    (decision,) = read_reviews(tmp_path).values()
    assert (decision.decision, decision.category) == ("edited", Category.UNANSWERABLE)


async def test_the_golden_set_becomes_a_dataset_over_the_corpus(
    offline_settings: Settings, document: ParsedDocument, tmp_path: Path
) -> None:
    drafts = await drafts_of(offline_settings, document)
    write_drafts(drafts, tmp_path / "golden")
    keys = iter(["a", "a", "a"])
    review(drafts, tmp_path / "golden", read=lambda _p: next(keys), write=lambda _l: None)
    questions = freeze(tmp_path / "golden", version="v1", summary="Unit.")
    pages = {
        HTML_URL.format(arxiv_id="2610.00001", version=1): PAPER.encode(),
        PDF_URL.format(arxiv_id="2610.00001", version=1): tiny_pdf(
            [["Retriever", "Recall", "Dense", "0.74"], ["The dense index costs more."]]
        ),
    }

    def fetch(url: str) -> bytes | None:
        if "verb=ListRecords" in url:
            return (
                (FIXTURES_DIR / "arxiv" / "oai_page_2.xml")
                .read_bytes()
                .replace(b"2610.00003", b"2610.00001")
            )
        return pages.get(url)

    selection = CorpusConfig.model_validate(
        {
            "name": "unit",
            "freshness_floor": "2026-10-20",
            "harvest_until": "2026-11-04",
            "models": {},
            "categories": ["cs.CL"],
            "license": CC_BY_4,
            "size": 1,
            "max_characters": 10_000,
        }
    )
    directory = tmp_path / "corpus"
    manifest = build_corpus(selection, ArxivClient(fetch=fetch, sleep=lambda _s: None), directory)
    corpus = Corpus(manifest, directory)

    reference = golden_dataset(questions, corpus, text="reference")
    assert reference.describe() == {
        "dataset": "golden/arxiv-fresh",
        "split": "reference",
        "examples": 3,
        "answerable": 2,
        "unanswerable": 1,
        "corpus_documents": 1,
    }
    factual, multi_hop, unanswerable = reference.examples
    assert (factual.kind, factual.answers) == ("factual", ("0.74",))
    assert factual.passages[0].document_id == "2610.00001v1"
    # Only the quote found word for word is a gold passage.
    assert [passage.text for passage in multi_hop.passages] == ["Dense | 0.74"]
    assert unanswerable.passages == ()

    naive = golden_dataset(questions, corpus, text="naive")
    (extracted,) = naive.corpus
    assert [section.title for section in extracted.sections] == ["Page 1", "Page 2"]
    # The table row quoted from the reference text is not in the PDF's text as a row:
    # what the naive extraction loses is exactly what the golden set can show.
    assert "Dense | 0.74" not in extracted.text
    assert (directory / "2610.00001v1.pypdf.json").is_file()
    assert corpus.extracted(manifest.documents[0]) == extracted


async def test_an_unanswerable_draft_is_reread_against_the_whole_paper(
    offline_settings: Settings, document: ParsedDocument
) -> None:
    drafts = await drafts_of(offline_settings, document)
    factual, _, unanswerable = drafts
    assert (unanswerable.characters_read, unanswerable.characters_total) == (
        document.char_count,
        document.char_count,
    )
    replies = [
        # The checker finds the answer and copies the sentence: the draft is flagged.
        '{"answered": true, "answer": "One machine.", "quote": "Measured on one machine."}',
        # It claims an answer but its "quote" is not in the paper: not shown to anyone.
        '{"answered": true, "answer": "An A100.", "quote": "We used an A100 GPU."}',
        '{"answered": false, "answer": "", "quote": ""}',
    ]
    client = client_with(offline_settings, "openai", "gpt-5.6-luna", replies)
    checker = UnanswerableChecker(
        client=client,
        prompts=PromptRegistry.from_settings(offline_settings),
        model=ModelRef.parse("openai/gpt-5.6-luna"),
    )
    flagged = await checker.check(unanswerable, document)
    assert flagged.found_elsewhere is not None
    assert flagged.found_elsewhere.section == "2.1 Cost"
    assert "the paper may answer it" in flagged.problems()[-1]
    assert (await checker.check(unanswerable, document)).found_elsewhere is None
    assert (await checker.check(unanswerable, document)).found_elsewhere is None
    # A draft that has an answer is not the checker's business: no call is made.
    assert await checker.check(factual, document) == factual
    sent = client.provider_for("openai", client.registry.get("openai"))
    assert len(sent.calls) == 3  # type: ignore[attr-defined]
    assert "2.1 Cost" in sent.calls[0].turns[-1].content  # type: ignore[attr-defined]
    shown: list[str] = []
    show(flagged, shown.append)
    assert any("A SECOND MODEL found this in “2.1 Cost”" in line for line in shown)
