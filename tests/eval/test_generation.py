"""Generation runner, judge, calibration and annotation, on scripted providers."""

import json
from pathlib import Path

import pytest

from llm_testbench.config import Settings
from llm_testbench.eval.annotate import annotate
from llm_testbench.eval.bias import (
    format_bias,
    padded,
    probe,
    reversed_excerpts,
    without_citations,
)
from llm_testbench.eval.calibration import (
    Material,
    build_items,
    calibrate,
    format_calibration,
    materialize,
    read_items,
    read_labels,
    write_items,
)
from llm_testbench.eval.context import Context, NoContext
from llm_testbench.eval.generation import (
    GenerationRun,
    attribution,
    format_generation,
    load_generation,
    run_generation,
    save_generation,
)
from llm_testbench.eval.judge import Judge, Rubric, render_material
from llm_testbench.eval.loaders.hotpotqa import HotpotQALoader
from llm_testbench.eval.loaders.qasper import QasperLoader
from llm_testbench.eval.loaders.squad import SquadV2Loader
from llm_testbench.eval.qa import QADataset, QAExample
from llm_testbench.eval.spend import SpendCapExceededError, SpendLedger
from llm_testbench.eval.suite import GenerationArmConfig, Suites, run_generation_arm
from llm_testbench.generation.answer import REFUSAL_SENTINEL, AnswerBuilder
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.prompts import PromptRegistry
from llm_testbench.llm.types import FinishReason, ModelRef
from tests.llm.fakes import FakeProvider, make_completion

GENERATOR = ModelRef.parse("anthropic/claude-sonnet-5-5")
JUDGE = ModelRef.parse("openai/gpt-5.6-luna")
REPO_ROOT = Path(__file__).resolve().parents[2]

# File order of the fixture: q-river (answerable), q-length (not), q-nobel (answerable),
# q-born (not).
ANSWERS = [
    "The Loire rises in the Massif Central [1].",  # right, cited
    REFUSAL_SENTINEL,  # correct refusal
    REFUSAL_SENTINEL,  # over-refusal
    "She was born in Warsaw [2].",  # answers the unanswerable, invents a citation
]


@pytest.fixture
def dataset(offline_settings: Settings) -> QADataset:
    return SquadV2Loader(offline_settings).load()


def client_with(
    offline_settings: Settings, backend: str, texts: list[str], model: str
) -> LLMClient:
    client = LLMClient.from_settings(offline_settings)
    script = [
        make_completion(text, model=model, backend=backend, input_tokens=400, output_tokens=20)
        for text in texts
    ]
    client.register_provider(backend, FakeProvider(backend, script=list(script)))
    return client


async def generate(
    offline_settings: Settings, dataset: QADataset, texts: list[str], **options: object
) -> GenerationRun:
    client = client_with(offline_settings, "anthropic", texts, "claude-sonnet-5-5")
    return await run_generation(
        dataset,
        client=client,
        builder=AnswerBuilder(PromptRegistry.from_settings(offline_settings)),
        model=GENERATOR,
        suite="unit",
        arm="gold",
        resamples=200,
        **options,  # type: ignore[arg-type]
    )


async def test_rates_are_computed_on_the_examples_they_apply_to(
    offline_settings: Settings, dataset: QADataset
) -> None:
    run = await generate(offline_settings, dataset, ANSWERS)
    metrics = run.metrics
    assert (metrics["correct_refusal"].mean, metrics["correct_refusal"].examples) == (0.5, 2)
    assert (metrics["over_refusal"].mean, metrics["over_refusal"].examples) == (0.5, 2)
    assert metrics["contains_answer"].mean == 0.5
    # Two answers were given: one cites a real excerpt, the other an excerpt that does not exist.
    assert (metrics["cited"].mean, metrics["cited"].examples) == (0.5, 2)
    assert metrics["invented_citation"].mean == 0.5
    assert run.answers[3].unknown_citations == (2,)
    assert run.generator == "anthropic/claude-sonnet-5-5"
    assert run.prompt["prompt.version"] == "2"
    # 4 calls of 400 input and 20 output tokens at $2 and $10 per million.
    assert run.cost_usd == pytest.approx(4 * (400 * 2 + 20 * 10) / 1e6)
    assert run.stability is None
    table = format_generation(run)
    assert "correct refusal (unanswerable)" in table
    assert "0.500" in table


async def test_repeats_measure_what_changes_between_runs(
    offline_settings: Settings, dataset: QADataset
) -> None:
    # Second pass on the first two questions: the first is now refused, the second reworded.
    texts = [*ANSWERS, REFUSAL_SENTINEL, REFUSAL_SENTINEL]
    run = await generate(offline_settings, dataset, texts, repeats=2, repeat_examples=2)
    assert len(run.answers) == 6
    assert len(run.scored()) == 4
    assert run.stability is not None
    assert (run.stability.examples, run.stability.runs) == (2, 2)
    assert run.stability.refusal_flips == 0.5
    assert run.stability.answer_changes == 0.5
    # The repeats do not enter the rates.
    assert run.metrics["over_refusal"].mean == 0.5


class ScriptedSearch:
    """A search that finds what the script says: the gold passages of the listed
    questions, one unrelated chunk for the others, at a known price."""

    retrieved = True

    def __init__(self, finds: set[str]) -> None:
        self._finds = finds

    def describe(self) -> dict[str, str | int | float | bool | None]:
        return {"context": "retrieved", "k": 5, "index_key": "unit"}

    def applies_to(self, example: QAExample) -> bool:
        return True

    async def context(self, example: QAExample) -> Context:
        evidence = example.evidence("unit")
        if example.example_id not in self._finds:
            evidence = evidence[:1] if len(evidence) > 1 else []
        return Context(evidence=tuple(evidence), cost_usd=0.001, latency_ms=12.0)


async def test_end_to_end_charges_a_failure_to_the_search_or_to_the_generator(
    offline_settings: Settings,
) -> None:
    dataset = HotpotQALoader(offline_settings).load()
    # h-nationality: both paragraphs found, right answer. h-river: found, wrong answer.
    # h-prize: one paragraph missing, and the generator refuses.
    texts = ["Yes, both were English [1][2].", "The Atlantic Ocean [2].", REFUSAL_SENTINEL]
    run = await generate(
        offline_settings,
        dataset,
        texts,
        context=ScriptedSearch({"h-nationality", "h-river"}),
    )
    split = attribution(run)
    assert split is not None
    assert (split.found_right, split.found_wrong) == (1, 1)
    assert (split.missed_right, split.missed_wrong, split.missed_refused) == (0, 1, 1)
    assert run.metrics["context_complete"].mean == pytest.approx(2 / 3)
    assert run.metrics["context_recall"].mean == pytest.approx((1 + 1 + 0.5) / 3)
    assert run.context == "retrieved"
    assert run.retrieval is not None
    assert run.retrieval["k"] == 5
    # The search is paid and waited for like the rest.
    assert run.cost_usd == pytest.approx(3 * ((400 * 2 + 20 * 10) / 1e6 + 0.001))
    assert run.answers[0].retrieval_ms == 12.0
    assert run.answers[0].retrieved == ("Ada Lovelace", "Charles Babbage")
    assert "found but wrong 1" in format_generation(run)


async def test_gold_context_leaves_out_the_questions_without_a_gold_passage(
    offline_settings: Settings,
) -> None:
    dataset = QasperLoader(offline_settings).load_qa()
    run = await generate(
        offline_settings, dataset, ["Retrieval [1].", "It splits [1].", "Yes [1]."]
    )
    # q4 is unanswerable and QASPER names no passage for it: nothing to ask it on.
    assert (len(run.scored()), run.examples_skipped) == (3, 1)
    assert "correct_refusal" not in run.metrics
    assert attribution(run) is None


async def test_an_answer_cut_by_the_output_cap_is_counted_not_hidden(
    offline_settings: Settings, dataset: QADataset
) -> None:
    """A model that reasons before it writes spends output tokens that are not in the text.
    When the cap is reached the answer comes back cut or empty, with no error: the run says
    how often."""
    client = LLMClient.from_settings(offline_settings)
    script = [
        make_completion(text, model="claude-sonnet-5-5", input_tokens=400, output_tokens=20)
        for text in ANSWERS
    ]
    # The second call spent its whole budget reasoning: nothing was written.
    script[1] = make_completion(
        "", model="claude-sonnet-5-5", input_tokens=400, output_tokens=64
    ).model_copy(update={"finish_reason": FinishReason.LENGTH})
    client.register_provider("anthropic", FakeProvider("anthropic", script=script))
    run = await run_generation(
        dataset,
        client=client,
        builder=AnswerBuilder(PromptRegistry.from_settings(offline_settings)),
        model=GENERATOR,
        suite="unit",
        arm="gold",
        max_output_tokens=64,
        resamples=200,
    )
    assert (run.metrics["truncated"].mean, run.metrics["truncated"].examples) == (0.25, 4)
    assert [answer.truncated for answer in run.answers] == [False, True, False, False]
    assert run.max_output_tokens == 64
    # An empty answer is not a refusal: the unanswerable question counts as answered.
    assert run.metrics["correct_refusal"].mean == 0.0
    assert "cut by the output cap" in format_generation(run)
    sent = client.provider_for("anthropic", client.registry.get("anthropic"))
    assert sent.calls[0].max_output_tokens == 64  # type: ignore[attr-defined]


async def test_closed_book_asks_without_any_document_through_its_own_prompt(
    offline_settings: Settings, dataset: QADataset
) -> None:
    client = client_with(
        offline_settings,
        "anthropic",
        ["The Massif Central.", REFUSAL_SENTINEL, REFUSAL_SENTINEL, "In Warsaw."],
        "claude-sonnet-5-5",
    )
    prompts = PromptRegistry.from_settings(offline_settings)
    run = await run_generation(
        dataset,
        client=client,
        builder=AnswerBuilder(prompts, prompt_name="closed_book"),
        model=GENERATOR,
        suite="unit",
        arm="closed-book",
        context=NoContext(),
        resamples=200,
    )
    assert run.context == "none (closed book)"
    assert run.prompt["name"] == "closed_book"
    # One of the two answerable questions is answered from memory.
    assert run.metrics["contains_answer"].mean == 0.5
    assert run.metrics["over_refusal"].mean == 0.5
    assert attribution(run) is None
    sent = client.provider_for("anthropic", client.registry.get("anthropic"))
    assert "No document is provided" in sent.calls[0].system  # type: ignore[attr-defined]


async def test_archive_round_trip_and_sample_mode(
    offline_settings: Settings, dataset: QADataset, tmp_path: Path
) -> None:
    run = await generate(offline_settings, dataset, ANSWERS)
    path = save_generation(run, tmp_path)
    assert load_generation(path) == run
    assert path.read_text(encoding="utf-8").count('\n  {"example_id"') == 4
    sample = await generate(offline_settings, dataset, ANSWERS, sample_mode=True)
    with pytest.raises(ValueError, match="not publishable"):
        save_generation(sample, tmp_path)


async def test_the_cap_stops_the_run_and_the_money_spent_is_recorded(
    offline_settings: Settings, dataset: QADataset, tmp_path: Path
) -> None:
    ledger_path = tmp_path / "spend.jsonl"
    one_call = (400 * 2 + 20 * 10) / 1e6
    ledger = SpendLedger(ledger_path, cap_usd=1.5 * one_call)
    with pytest.raises(SpendCapExceededError, match="spend cap reached"):
        await generate(offline_settings, dataset, ANSWERS, ledger=ledger)
    # Two calls went out before the cap was seen; they are on the ledger.
    (line,) = ledger_path.read_text(encoding="utf-8").splitlines()
    assert json.loads(line)["usd"] == pytest.approx(2 * one_call)
    assert SpendLedger(ledger_path, cap_usd=1.0).recorded_usd() == pytest.approx(2 * one_call)
    with pytest.raises(SpendCapExceededError, match="unknown price"):
        SpendLedger(ledger_path, cap_usd=1.0).charge(None, "a model without a price")


async def test_generation_arm_in_sample_mode_uses_a_scripted_generator(tmp_path: Path) -> None:
    settings = Settings(
        fixtures_dir=REPO_ROOT / "tests" / "fixtures", data_dir=tmp_path, sample=True
    )
    arm = GenerationArmConfig(name="squad-gold", dataset="squad_v2", repeats=2, repeat_examples=2)
    run = await run_generation_arm(
        "gate", arm, settings=settings, client=LLMClient.from_settings(settings), ledger=None
    )
    assert not run.publishable
    assert run.metrics["cited"].mean == 1.0
    assert run.metrics["correct_refusal"].mean == 0.0
    assert run.stability is not None
    assert run.stability.answer_changes == 0.0


def test_the_versioned_generation_suite_is_lean_and_capped() -> None:
    suites = Suites.load(REPO_ROOT / "config" / "eval_suites.toml")
    assert suites.budget.cap_usd == 10.0
    (arm,) = suites.get("generation-baseline").generation
    assert (arm.max_examples, arm.repeats, arm.repeat_examples) == (100, 3, 50)
    assert suites.get("gate").select(["squad-gold"])[0] == ()


async def test_judge_returns_a_verdict_with_its_reasons_and_its_price(
    offline_settings: Settings, dataset: QADataset
) -> None:
    replies = [
        '{"justification": "The excerpt states the Massif Central.", "verdict": "yes"}',
        '{"justification": "Warsaw is not in the excerpts.", "verdict": "no"}',
    ]
    client = client_with(offline_settings, "openai", replies, "gpt-5.6-luna")
    judge = Judge(
        client=client, prompts=PromptRegistry.from_settings(offline_settings), model=JUDGE
    )
    example = dataset.examples[0]
    evidence = example.evidence("squad_v2")
    supported = await judge.grade(
        Rubric.GROUNDEDNESS, question=example.question, answer=ANSWERS[0], evidence=evidence
    )
    assert supported.label is True
    assert supported.justification.startswith("The excerpt states")
    assert (supported.judge, supported.served_model) == ("openai/gpt-5.6-luna", "gpt-5.6-luna")
    assert supported.prompt_version == "1"
    assert supported.cost_usd == pytest.approx((400 * 0.2 + 20 * 1.2) / 1e6)
    unsupported = await judge.grade(
        Rubric.GROUNDEDNESS, question=example.question, answer=ANSWERS[3], evidence=evidence
    )
    assert unsupported.label is False


def test_the_judge_reads_the_excerpts_for_groundedness_only(dataset: QADataset) -> None:
    example = dataset.examples[0]
    evidence = example.evidence("squad_v2")
    grounded = render_material(
        Rubric.GROUNDEDNESS, question=example.question, answer="A [1].", evidence=evidence
    )
    relevant = render_material(
        Rubric.RELEVANCE, question=example.question, answer="A [1].", evidence=evidence
    )
    assert "Excerpts:\n[1] squad_v2 › Loire › gold passage" in grounded
    assert "Excerpts" not in relevant
    assert "Answer to grade:\nA [1]." in relevant


async def test_calibration_items_annotation_and_agreement(
    offline_settings: Settings, dataset: QADataset, tmp_path: Path
) -> None:
    # Every question answered, so that there are four items to draw from.
    texts = [f"Answer number {n} [1]." for n in range(4)]
    run = await generate(offline_settings, dataset, texts)
    # 4 answers: at most a fifth swapped each way, so none; force one of each to see them.
    items = build_items(run, dataset, size=4, seed=1)
    assert [item.item_id for item in items] == ["c001", "c002", "c003", "c004"]
    assert {item.kind for item in items} == {"natural"}
    assert all(materialize(item, dataset).answer == item.answer for item in items)
    assert build_items(run, dataset, size=4, seed=1) == items  # seeded

    directory = tmp_path / "judge_calibration"
    write_items(items, directory)
    assert read_items(directory) == items

    # The human: "?" shows the rules, then y/n, a note; second item skipped; third n/y;
    # then q stops. Two labels, saved as they are given.
    keys = iter(["?", "y", "n", "wrong topic", "s", "n", "y", "", "q"])
    shown: list[str] = []
    added = annotate(items, dataset, directory, read=lambda _prompt: next(keys), write=shown.append)
    assert added == 2
    labels = read_labels(directory)
    assert set(labels) == {"c001", "c003"}
    assert (labels["c001"].groundedness, labels["c001"].relevance) == (True, False)
    assert labels["c001"].note == "wrong topic"
    screen = "\n".join(shown)
    assert "QUESTION" in screen
    assert "EXCERPT [1]" in screen
    # Blind: neither the kind of the item nor any verdict is on screen.
    assert "natural" not in screen
    assert "other_passage" not in screen
    # Resuming asks only for what is missing.
    assert annotate(items, dataset, directory, read=lambda _prompt: "q", write=shown.append) == 0

    # The judge agrees with the human on c001 (yes / no) and differs on c003 (says yes / yes
    # where the human said no / yes).
    replies = [
        '{"justification": "found", "verdict": "yes"}',
        '{"justification": "another topic", "verdict": "no"}',
        '{"justification": "found", "verdict": "yes"}',
        '{"justification": "on topic", "verdict": "yes"}',
    ]
    client = client_with(offline_settings, "openai", replies, "gpt-5.6-luna")
    judge = Judge(
        client=client, prompts=PromptRegistry.from_settings(offline_settings), model=JUDGE
    )
    report = await calibrate(items, labels, dataset, [judge])
    assert report.items == 2
    by_rubric = {row.rubric: row for row in report.judges}
    assert by_rubric[Rubric.GROUNDEDNESS].agreement.observed == 0.5
    assert by_rubric[Rubric.GROUNDEDNESS].disagreements == ("c003",)
    assert by_rubric[Rubric.RELEVANCE].agreement.observed == 1.0
    assert report.verdicts["openai/gpt-5.6-luna"]["c001"]["relevance"].justification == (
        "another topic"
    )
    assert "openai/gpt-5.6-luna" in format_calibration(report)
    with pytest.raises(ValueError, match="no human label"):
        await calibrate(items, {}, dataset, [judge])


def test_swapped_items_take_another_passage_or_another_question(
    offline_settings: Settings, dataset: QADataset
) -> None:
    from llm_testbench.eval.generation import AnswerResult

    # Ten answered results on the four fixture questions are enough to allow two swaps each way.
    examples = list(dataset.examples) * 3
    answers = tuple(
        AnswerResult(
            example_id=f"{example.example_id}",
            answerable=example.answerable,
            answer=f"Answer {n} [1].",
            refused=False,
            metrics={},
            latency_ms=1.0,
            cost_usd=0.0,
            input_tokens=1,
            output_tokens=1,
        )
        for n, example in enumerate(examples[:10])
    )
    run = GenerationRun.model_construct(run_id="r", answers=answers)
    items = build_items(run, dataset, size=10, other_passage=2, other_question=2, seed=3)
    kinds = [item.kind for item in items]
    assert (kinds.count("other_passage"), kinds.count("other_question")) == (2, 2)
    for item in items:
        if item.kind == "other_passage":
            assert item.passages_from != item.answer_from
            assert item.question_from == item.answer_from
        if item.kind == "other_question":
            assert item.question_from != item.answer_from
            assert item.passages_from == item.answer_from


async def test_bias_probes_compare_each_change_with_doing_nothing(
    offline_settings: Settings, dataset: QADataset
) -> None:
    example = dataset.examples[0]
    material = Material(
        question=example.question,
        evidence=tuple(example.evidence(dataset.info.key)),
        answer="The Loire rises in the Massif Central [1].",
    )
    plain = material.model_copy(update={"answer": "The Loire rises in the Massif Central."})
    assert padded(material).answer.startswith(material.answer)
    assert without_citations(material).answer == plain.answer
    assert reversed_excerpts(material) == material  # one excerpt: nothing to reverse

    yes = '{"justification": "Stated in the excerpt.", "verdict": "yes"}'
    no = '{"justification": "No marker, no support.", "verdict": "no"}'
    # Order of the calls: both rubrics on the two items as they are (4), then per change and
    # rubric: repeat (2 + 2), padded (2 + 2), without_citations (1 + 1: the plain answer has
    # no citation to lose). The judge flips once, on groundedness, when the marker goes.
    replies = [yes] * 4 + [yes] * 4 + [yes] * 4 + [no, yes]
    judge = Judge(
        client=client_with(offline_settings, "openai", replies, "gpt-5.6-luna"),
        prompts=PromptRegistry.from_settings(offline_settings),
        model=JUDGE,
    )
    results = await probe([material, plain], judge)
    by_key = {(row.perturbation, row.rubric): row for row in results}
    # A single excerpt cannot be reordered: the position probe has no item and no row.
    assert ("reversed_excerpts", Rubric.GROUNDEDNESS) not in by_key
    control = by_key[("repeat", Rubric.GROUNDEDNESS)]
    assert (control.items, control.flips, control.bias) == (2, 0, "control")
    lost = by_key[("without_citations", Rubric.GROUNDEDNESS)]
    assert (lost.items, lost.flips, lost.to_no, lost.to_yes) == (1, 1, 1, 0)
    assert by_key[("without_citations", Rubric.RELEVANCE)].flips == 0
    assert by_key[("padded", Rubric.GROUNDEDNESS)].flip_rate == 0.0
    table = format_bias(results)
    assert "without_citations" in table
    assert "1 to no" in table
    with pytest.raises(KeyError, match="unknown perturbation"):
        await probe([material], judge, ["shouting"])
