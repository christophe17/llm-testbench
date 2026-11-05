"""Command line of the golden set.

    python -m llm_testbench.eval.golden.cli draft     # a model writes the drafts (paid)
    python -m llm_testbench.eval.golden.cli probe     # closed-book check of the drafts (paid)
    python -m llm_testbench.eval.golden.cli review    # a person decides, in the terminal
    python -m llm_testbench.eval.golden.cli freeze --version v1 --summary "..."
    python -m llm_testbench.eval.golden.cli status

The two paid steps go through the spend ledger and its cap, like every run of the harness.
"""

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

from llm_testbench.config import Settings, find_repo_root, get_settings, load_env_file
from llm_testbench.eval.cli import spend_ledger
from llm_testbench.eval.corpus.build import Corpus
from llm_testbench.eval.corpus.cli import load_corpus
from llm_testbench.eval.corpus.manifest import CORPUS_CONFIG, CorpusConfig, GoldenConfig
from llm_testbench.eval.golden.drafting import (
    Drafter,
    UnanswerableChecker,
    assign_categories,
    pick_documents,
)
from llm_testbench.eval.golden.review import review
from llm_testbench.eval.golden.store import (
    GOLDEN_DIR,
    freeze,
    read_drafts,
    read_questions,
    read_reviews,
    write_drafts,
)
from llm_testbench.eval.golden.types import Category, Draft
from llm_testbench.eval.metrics.generation import contains_answer
from llm_testbench.eval.spend import SpendLedger
from llm_testbench.generation.answer import AnswerBuilder, is_refusal
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.governance import DataClass
from llm_testbench.llm.prompts import PromptRegistry
from llm_testbench.llm.types import ModelRef

CLOSED_BOOK_PROMPT = "closed_book"


def golden_config(settings: Settings) -> GoldenConfig:
    config = CorpusConfig.load(settings.resolved_config_dir() / CORPUS_CONFIG)
    if config.golden is None:
        raise SystemExit("config/corpus.toml has no [golden] table")
    return config.golden


async def draft_all(
    corpus: Corpus,
    config: GoldenConfig,
    *,
    client: LLMClient,
    prompts: PromptRegistry,
    ledger: SpendLedger | None,
    directory: Path,
    limit: int | None = None,
) -> list[Draft]:
    """The drafts of the configured documents, written to ``directory`` after each
    document: a run can be stopped, or limited to a few documents to see what one costs,
    and resumed. Documents that already have drafts are not asked again. The manifest must
    vouch for freshness against the drafter too: a model that has read the paper writes
    guessable questions."""
    manifest = corpus.manifest
    if not manifest.fresh_for(config.drafter):
        raise SystemExit(
            f"the corpus is not established as fresh for {config.drafter}: add the model to "
            "config/corpus.toml and rebuild the manifest"
        )
    doc_ids = pick_documents(
        [entry.doc_id for entry in manifest.documents], config.documents, config.seed
    )
    drafter = Drafter(
        client=client,
        prompts=prompts,
        model=ModelRef.parse(config.drafter),
        ledger=ledger,
        max_characters=config.max_characters,
    )
    drafts = read_drafts(directory)
    done = {draft.doc_id for draft in drafts}
    asked = 0
    try:
        for doc_id, kinds in zip(
            doc_ids, assign_categories(len(doc_ids), config.per_document), strict=True
        ):
            if doc_id in done:
                continue
            if limit is not None and asked >= limit:
                break
            document = corpus.reference(manifest.entry(doc_id))
            written = await drafter.draft(document, kinds)
            asked += 1
            drafts.extend(written)
            write_drafts(drafts, directory)
            spent = "" if ledger is None else f" — ${ledger.session_usd:.3f} so far"
            sys.stderr.write(f"  {doc_id}: {len(written)} of {len(kinds)} drafts{spent}\n")
    finally:
        if ledger is not None:
            ledger.commit(f"golden set drafts ({config.drafter}, {asked} documents)")
    return drafts


async def probe_all(
    drafts: list[Draft],
    *,
    client: LLMClient,
    prompts: PromptRegistry,
    model: ModelRef,
    ledger: SpendLedger | None,
) -> list[Draft]:
    """Each draft asked to the generator with no document. A right answer means the
    question can be guessed, and the reviewer is told."""
    builder = AnswerBuilder(prompts, prompt_name=CLOSED_BOOK_PROMPT)
    probed: list[Draft] = []
    try:
        for draft in drafts:
            if ledger is not None:
                ledger.check()
            request = builder.build_request(
                draft.question, [], model=model, data_class=DataClass.PUBLIC
            )
            completion = await client.complete(request, use_cache=False)
            if ledger is not None:
                ledger.charge(completion.cost_usd, f"closed-book probe {model}")
            text = completion.text.strip()
            right = (
                draft.answerable and not is_refusal(text) and contains_answer(text, [draft.answer])
            )
            probed.append(
                draft.model_copy(update={"closed_book_answer": text, "closed_book_correct": right})
            )
    finally:
        if ledger is not None:
            ledger.commit(f"golden set closed-book probe ({model})")
    return probed


async def check_all(
    drafts: list[Draft],
    corpus: Corpus,
    config: GoldenConfig,
    *,
    client: LLMClient,
    prompts: PromptRegistry,
    ledger: SpendLedger | None,
) -> list[Draft]:
    """Each draft marked unanswerable, reread against its whole paper by the checker."""
    checker = UnanswerableChecker(
        client=client, prompts=prompts, model=ModelRef.parse(config.checker), ledger=ledger
    )
    checked: list[Draft] = []
    try:
        for draft in drafts:
            if draft.answerable:
                checked.append(draft)
                continue
            document = corpus.reference(corpus.manifest.entry(draft.doc_id))
            checked.append(await checker.check(draft, document))
    finally:
        if ledger is not None:
            ledger.commit(f"golden set unanswerable check ({config.checker})")
    return checked


def status(directory: Path) -> str:
    drafts = read_drafts(directory)
    reviews = read_reviews(directory)
    questions = read_questions(directory)
    kinds = Counter(draft.category for draft in drafts)
    decisions = Counter(item.decision for item in reviews.values())
    frozen = Counter(question.category for question in questions)
    not_found = sum(1 for draft in drafts for quote in draft.quotes if not quote.found)
    quotes = sum(len(draft.quotes) for draft in drafts)
    guessed = sum(1 for draft in drafts if draft.closed_book_correct)
    elsewhere = sum(1 for draft in drafts if draft.found_elsewhere is not None)
    lines = [
        f"drafts: {len(drafts)} — "
        + ", ".join(f"{kinds[category]} {category.value}" for category in Category),
        f"quotes: {quotes}, of which {not_found} not found word for word in their document",
        f"answered correctly without any document: {guessed}",
        f"marked unanswerable although the whole paper may answer: {elsewhere}",
        f"reviewed: {len(reviews)} — "
        + ", ".join(f"{count} {decision}" for decision, count in sorted(decisions.items())),
        f"frozen set: {len(questions)} — "
        + ", ".join(f"{frozen[category]} {category.value}" for category in Category),
    ]
    return "\n".join(lines)


async def _probe(settings: Settings, directory: Path) -> list[Draft]:
    client = LLMClient.from_settings(settings)
    prompts = PromptRegistry.from_settings(settings)
    ledger = spend_ledger(settings)
    probed = await probe_all(
        read_drafts(directory),
        client=client,
        prompts=prompts,
        model=client.registry.defaults.generator,
        ledger=ledger,
    )
    return await check_all(
        probed,
        load_corpus(settings),
        golden_config(settings),
        client=client,
        prompts=prompts,
        ledger=ledger,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    draft = commands.add_parser("draft", help="a model writes the drafts (paid, under the cap)")
    draft.add_argument("--limit", type=int, default=None, help="at most this many documents")
    commands.add_parser(
        "probe",
        help="two checks of the drafts: closed book, and unanswerable ones against the "
        "whole paper (paid, under the cap)",
    )
    again = commands.add_parser("review", help="decide on each draft, in the terminal")
    again.add_argument("--again", action="store_true", help="also show drafts already reviewed")
    frozen = commands.add_parser("freeze", help="write questions.jsonl and the changelog")
    frozen.add_argument("--version", required=True)
    frozen.add_argument("--summary", required=True)
    commands.add_parser("status", help="where the golden set stands")
    args = parser.parse_args(argv)
    load_env_file()
    settings = get_settings()
    directory = find_repo_root() / GOLDEN_DIR
    if args.command == "draft":
        client = LLMClient.from_settings(settings)
        asyncio.run(
            draft_all(
                load_corpus(settings),
                golden_config(settings),
                client=client,
                prompts=PromptRegistry.from_settings(settings),
                ledger=spend_ledger(settings),
                directory=directory,
                limit=args.limit,
            )
        )
    elif args.command == "probe":
        write_drafts(asyncio.run(_probe(settings, directory)), directory)
    elif args.command == "review":
        review(read_drafts(directory), directory, again=args.again)
        return 0
    elif args.command == "freeze":
        questions = freeze(directory, version=args.version, summary=args.summary)
        sys.stdout.write(f"{args.version}: {len(questions)} questions frozen\n")
    sys.stdout.write(status(directory) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
