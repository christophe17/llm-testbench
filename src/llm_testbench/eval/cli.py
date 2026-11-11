"""The harness from the command line: ``python -m llm_testbench.eval.cli <command>``.

- ``run``: run the arms of a suite (``config/eval_suites.toml``), print the results, save
  the retrieval runs to the history table when a database is configured, archive the full
  runs under ``data/results/runs/`` and say how each differs from the run it replaces;
- ``compare``: two archived retrieval arms of a suite, query by query;
- ``report``: the comparative HTML report, rebuilt from the archived runs;
- ``gate``: the regression gate, always in sample mode (pre-push hook, CI);
- ``calibration-set``, ``annotate``, ``calibrate``: the judge against a human (phase 2.3):
  draw the items from an archived generation run, label them by hand, measure agreement.

In sample mode (``LLM_TESTBENCH_SAMPLE=1``) nothing is archived and nothing is spent: a
sample run checks the mechanics, it is not a number. Every paid run goes through the spend
ledger and its cap (``eval/spend.py``).
"""

import argparse
import asyncio
import sys
from pathlib import Path

from psycopg import AsyncConnection, OperationalError

from llm_testbench.config import Settings, find_repo_root, get_settings, load_env_file
from llm_testbench.eval.annotate import annotate
from llm_testbench.eval.bias import format_bias, probe, save_bias
from llm_testbench.eval.calibration import (
    CALIBRATION_DIR,
    build_items,
    calibrate,
    format_calibration,
    materialize,
    read_items,
    read_labels,
    save_calibration,
    write_items,
)
from llm_testbench.eval.compare import compare_runs, describe_difference
from llm_testbench.eval.gate import (
    BASELINE_PATH,
    GATE_SUITE,
    GateBaseline,
    GatedRun,
    check_gate,
    format_findings,
    gate_passes,
)
from llm_testbench.eval.generation import (
    GenerationRun,
    format_generation_run,
    load_generation_run,
    save_generation_run,
)
from llm_testbench.eval.judge import Judge
from llm_testbench.eval.loaders.squad import SquadV2Loader
from llm_testbench.eval.qa import QADataset
from llm_testbench.eval.report import write_report
from llm_testbench.eval.retrieval import (
    RetrievalRun,
    format_retrieval_runs,
    load_retrieval_run,
    save_retrieval_run,
)
from llm_testbench.eval.run_store import RunStore
from llm_testbench.eval.spend import LEDGER_PATH, SpendLedger
from llm_testbench.eval.suite import Suites, run_generation_arm, run_retrieval_arm
from llm_testbench.ingest.store import PgVectorStore
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.prompts import PromptRegistry
from llm_testbench.llm.types import ModelRef

DEFAULT_SUITE = "retrieval-baseline"
GENERATION_SUITE = "generation-baseline"


def archive_path(results_dir: Path, suite: str, arm: str) -> Path:
    return results_dir / "runs" / suite / f"{arm}.json"


def spend_ledger(settings: Settings) -> SpendLedger | None:
    """The ledger of the paid runs; none in sample mode, where nothing is paid."""
    if settings.sample or settings.fixtures_dir is not None:
        return None
    cap = Suites.from_settings(settings).budget.cap_usd
    return SpendLedger(find_repo_root() / LEDGER_PATH, cap)


async def run_retrieval_suite(
    suite_name: str,
    arm_names: list[str] | None,
    *,
    settings: Settings,
    results_dir: Path | None,
    record_history: bool = True,
    echo: bool = True,
) -> list[RetrievalRun]:
    """The retrieval arms of a suite."""
    suite = Suites.from_settings(settings).get(suite_name)
    arms, _ = suite.select(arm_names)
    if not arms:
        return []
    client = LLMClient.from_settings(settings)
    ledger = spend_ledger(settings)
    history = RunStore(settings.database_url) if settings.database_url and record_history else None
    if history is not None:
        await history.ensure_schema()
    needs_index = any(arm.retriever == "dense" for arm in arms)
    store = (
        PgVectorStore.from_url(settings.database_url)
        if settings.database_url and needs_index
        else None
    )
    runs: list[RetrievalRun] = []
    if store is not None:
        await store.open()
    try:
        for arm in arms:
            if echo:
                sys.stderr.write(f"→ {arm.name} ({arm.dataset})\n")
            if ledger is not None:
                ledger.check()
            run = await run_retrieval_arm(
                suite_name, suite, arm, settings=settings, client=client, store=store
            )
            runs.append(run)
            if ledger is not None:
                build_cost = run.index.cost_usd if run.index is not None else 0.0
                ledger.charge((build_cost or 0.0) + (run.cost_usd or 0.0), arm.name)
                ledger.commit(f"retrieval {suite_name}/{arm.name}")
            if history is not None:
                await history.save(run)
            if results_dir is not None and run.publishable:
                previous = archive_path(results_dir, suite_name, arm.name)
                if echo and previous.is_file():
                    sys.stderr.write(f"  {against_archive(run, load_retrieval_run(previous))}\n")
                save_retrieval_run(run, results_dir)
    finally:
        if store is not None:
            await store.close()
    return runs


async def run_generation_suite(
    suite_name: str,
    arm_names: list[str] | None,
    *,
    settings: Settings,
    results_dir: Path | None,
    echo: bool = True,
) -> list[GenerationRun]:
    """The generation arms of a suite."""
    suite = Suites.from_settings(settings).get(suite_name)
    _, arms = suite.select(arm_names)
    if not arms:
        return []
    client = LLMClient.from_settings(settings)
    ledger = spend_ledger(settings)
    searches = any(arm.context == "retrieved" for arm in arms)
    store = (
        PgVectorStore.from_url(settings.database_url)
        if settings.database_url and searches
        else None
    )
    runs: list[GenerationRun] = []
    if store is not None:
        await store.open()
    try:
        for arm in arms:
            if echo:
                sys.stderr.write(f"→ {arm.name} ({arm.dataset})\n")
            run = await run_generation_arm(
                suite_name, arm, settings=settings, client=client, ledger=ledger, store=store
            )
            runs.append(run)
            if results_dir is not None and run.publishable:
                save_generation_run(run, results_dir)
    finally:
        if store is not None:
            await store.close()
    return runs


def against_archive(run: RetrievalRun, archived: RetrievalRun) -> str:
    """What this full run changes compared with the archived one it is about to replace:
    the quality guard the sample-mode gate cannot be."""
    origin = f"archived run of {archived.created_at:%Y-%m-%d} ({archived.git_sha or 'no commit'})"
    try:
        return f"against the {origin}: {describe_difference(compare_runs(run, archived))}"
    except (ValueError, KeyError):
        return f"against the {origin}: not comparable (other queries or metrics)"


async def database_reachable(url: str | None) -> bool:
    if not url:
        return False
    try:
        async with await AsyncConnection.connect(url, connect_timeout=3):
            return True
    except OperationalError:
        return False


async def run_gate(settings: Settings, *, require_db: bool) -> tuple[list[GatedRun], list[str]]:
    """The gate suite, forced into sample mode whatever the environment says: it can
    neither download a dataset nor spend a cent. Returns the runs and the skipped arms."""
    sample = settings.model_copy(
        update={"sample": True, "fixtures_dir": find_repo_root() / "tests" / "fixtures"}
    )
    suite = Suites.from_settings(sample).get(GATE_SUITE)
    skipped: list[str] = []
    if not await database_reachable(sample.database_url):
        if require_db:
            raise SystemExit("evaluation gate: a database is required here and none answers")
        # A laptop with its cluster down still gets the arms that need no database; a
        # hook that fails whenever the cluster is off is a hook that gets bypassed.
        skipped = [arm.name for arm in suite.retrieval if arm.retriever == "dense"]
        skipped += [arm.name for arm in suite.generation if arm.context == "retrieved"]
        sample = sample.model_copy(update={"database_url": None})
    names = [name for name in suite.arm_names() if name not in skipped]
    runs: list[GatedRun] = []
    runs += await run_retrieval_suite(
        GATE_SUITE, names, settings=sample, results_dir=None, record_history=False, echo=False
    )
    runs += await run_generation_suite(
        GATE_SUITE, names, settings=sample, results_dir=None, echo=False
    )
    return runs, skipped


async def run_everything(
    suite: str, arms: list[str] | None, *, settings: Settings, results_dir: Path | None
) -> tuple[list[RetrievalRun], list[GenerationRun]]:
    """Retrieval arms then generation arms, on ONE event loop: an HTTP client belongs to
    the loop that opened it, and a second ``asyncio.run`` would leave the first one's
    connections to be closed on a loop that no longer exists."""
    retrieval = await run_retrieval_suite(suite, arms, settings=settings, results_dir=results_dir)
    generation = await run_generation_suite(suite, arms, settings=settings, results_dir=results_dir)
    return retrieval, generation


def _run_command(args: argparse.Namespace, settings: Settings) -> int:
    results_dir = None if args.no_archive else find_repo_root() / "data" / "results"
    retrieval, generation = asyncio.run(
        run_everything(args.suite, args.arm, settings=settings, results_dir=results_dir)
    )
    if retrieval:
        sys.stdout.write(format_retrieval_runs(retrieval) + "\n")
        if not settings.database_url:
            sys.stderr.write("no LLM_TESTBENCH_DATABASE_URL: runs not saved to the history\n")
    for run in generation:
        sys.stdout.write(format_generation_run(run) + "\n\n")
    ledger = spend_ledger(settings)
    if ledger is not None:
        sys.stderr.write(f"spent so far: ${ledger.spent_usd:.2f} of ${ledger.cap_usd:.2f}\n")
    return 0


def _compare_command(args: argparse.Namespace) -> int:
    results_dir = find_repo_root() / "data" / "results"
    for arm in (args.candidate, args.baseline):
        if not archive_path(results_dir, args.suite, arm).is_file():
            raise SystemExit(f"no archived run for arm {arm!r}: make eval ARMS={arm}")
    candidate = load_retrieval_run(archive_path(results_dir, args.suite, args.candidate))
    baseline = load_retrieval_run(archive_path(results_dir, args.suite, args.baseline))
    sys.stdout.write(format_retrieval_runs([baseline, candidate]) + "\n")
    difference = compare_runs(candidate, baseline, args.metric)
    sys.stdout.write(
        f"{args.candidate} against {args.baseline}, {len(candidate.queries)} queries: "
        f"{describe_difference(difference, args.metric)}\n"
    )
    return 0


def _report_command(args: argparse.Namespace, settings: Settings) -> int:
    root = find_repo_root()
    output = args.output or root / "build" / "eval" / f"{args.suite}.html"
    suite = Suites.from_settings(settings).get(args.suite)
    path, count = write_report(args.suite, suite, root / "data" / "results", output)
    sys.stdout.write(f"report of {count} archived runs: {path}\n")
    return 0


def _gate_command(args: argparse.Namespace, settings: Settings) -> int:
    baseline_path = find_repo_root() / BASELINE_PATH
    runs, skipped = asyncio.run(run_gate(settings, require_db=args.require_db or args.update))
    if args.update:
        GateBaseline.from_runs(runs).save(baseline_path)
        sys.stdout.write(f"gate baseline recorded: {baseline_path} ({len(runs)} arms)\n")
        return 0
    if not baseline_path.is_file():
        sys.stderr.write(f"no gate baseline at {baseline_path}: make eval-gate-update\n")
        return 1
    findings = check_gate(
        runs, GateBaseline.load(baseline_path), max_drop=args.max_drop, skipped=skipped
    )
    sys.stdout.write(format_findings(findings) + "\n")
    return 0 if gate_passes(findings) else 1


def _calibration_source(args: argparse.Namespace, settings: Settings) -> GenerationRun:
    path = archive_path(find_repo_root() / "data" / "results", args.suite, args.arm)
    if not path.is_file():
        raise SystemExit(f"no archived generation run at {path}: make eval SUITE={args.suite}")
    return load_generation_run(path)


def _calibration_dataset(run: GenerationRun, settings: Settings) -> QADataset:
    """The questions the run was made on: the same subsample, drawn again from its seed."""
    seed = run.dataset.get("subsample_seed")
    return SquadV2Loader(settings).load(
        str(run.dataset["split"]),
        max_examples=int(run.dataset["examples"]) if seed is not None else None,
        seed=int(seed) if seed is not None else 0,
    )


def _calibration_set_command(args: argparse.Namespace, settings: Settings) -> int:
    directory = find_repo_root() / CALIBRATION_DIR
    if read_labels(directory) and not args.force:
        raise SystemExit(
            f"{directory} already holds human labels: rebuilding the items would orphan them "
            "(--force to do it anyway)"
        )
    run = _calibration_source(args, settings)
    dataset = _calibration_dataset(run, settings)
    items = build_items(run, dataset, size=args.size, seed=args.seed)
    path = write_items(items, directory)
    kinds = {
        kind: sum(1 for item in items if item.kind == kind)
        for kind in sorted({item.kind for item in items})
    }
    sys.stdout.write(f"{len(items)} items written to {path} ({kinds}); next: make eval-annotate\n")
    return 0


def _annotate_command(args: argparse.Namespace, settings: Settings) -> int:
    directory = find_repo_root() / CALIBRATION_DIR
    items = read_items(directory)
    run = _calibration_source(args, settings)
    dataset = _calibration_dataset(run, settings)
    annotate(items, dataset, directory)
    return 0


def _calibrate_command(args: argparse.Namespace, settings: Settings) -> int:
    root = find_repo_root()
    directory = root / CALIBRATION_DIR
    run = _calibration_source(args, settings)
    dataset = _calibration_dataset(run, settings)
    client = LLMClient.from_settings(settings)
    prompts = PromptRegistry.from_settings(settings)
    ledger = spend_ledger(settings)
    judges = [
        Judge(client=client, prompts=prompts, model=ModelRef.parse(name), ledger=ledger)
        for name in args.judge
    ]
    try:
        report = asyncio.run(
            calibrate(read_items(directory), read_labels(directory), dataset, judges)
        )
    finally:
        if ledger is not None:
            ledger.commit(f"judge calibration ({', '.join(args.judge)})")
    sys.stdout.write(format_calibration(report) + "\n")
    path = save_calibration(report, root / "data" / "results")
    sys.stdout.write(f"→ {path} (justifications included)\n")
    return 0


def _bias_command(args: argparse.Namespace, settings: Settings) -> int:
    root = find_repo_root()
    directory = root / CALIBRATION_DIR
    run = _calibration_source(args, settings)
    dataset = _calibration_dataset(run, settings)
    materials = [materialize(item, dataset) for item in read_items(directory)]
    client = LLMClient.from_settings(settings)
    ledger = spend_ledger(settings)
    judge = Judge(
        client=client,
        prompts=PromptRegistry.from_settings(settings),
        model=ModelRef.parse(args.judge[0]),
        ledger=ledger,
    )
    try:
        results = asyncio.run(probe(materials, judge))
    finally:
        if ledger is not None:
            ledger.commit(f"judge bias probes ({args.judge[0]})")
    sys.stdout.write(format_bias(results) + "\n")
    path = save_bias(results, root / "data" / "results")
    sys.stdout.write(f"→ {path}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_env_file()  # .env at the repository root; the environment wins
    parser = argparse.ArgumentParser(description="Evaluation harness.")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="run the arms of a suite")
    run.add_argument("--suite", default=DEFAULT_SUITE)
    run.add_argument("--arm", action="append", help="only this arm (repeatable)")
    run.add_argument("--no-archive", action="store_true", help="do not write data/results")

    compare = commands.add_parser("compare", help="two archived arms, query by query")
    compare.add_argument("--suite", default=DEFAULT_SUITE)
    compare.add_argument("--baseline", required=True)
    compare.add_argument("--candidate", required=True)
    compare.add_argument("--metric", default="ndcg_at_10")

    report = commands.add_parser("report", help="HTML report from the archived runs")
    report.add_argument("--suite", default=DEFAULT_SUITE)
    report.add_argument("--output", type=Path, default=None, help="default: build/eval/")

    gate = commands.add_parser("gate", help="regression gate in sample mode")
    gate.add_argument("--update", action="store_true", help="record the current scores")
    gate.add_argument("--require-db", action="store_true", help="fail without a database (CI)")
    gate.add_argument("--max-drop", type=float, default=0.0, help="tolerated drop per metric")

    for name, text in (
        ("calibration-set", "draw the calibration items from an archived generation run"),
        ("annotate", "label the calibration items by hand"),
        ("calibrate", "judges against the human labels (Cohen's kappa)"),
        ("bias", "does a judge's verdict move when only the form of the answer does"),
    ):
        sub = commands.add_parser(name, help=text)
        sub.add_argument("--suite", default=GENERATION_SUITE)
        sub.add_argument("--arm", default="squad-gold-sonnet")
        if name == "calibration-set":
            sub.add_argument("--size", type=int, default=50)
            sub.add_argument("--seed", type=int, default=0)
            sub.add_argument("--force", action="store_true")
        if name in ("calibrate", "bias"):
            sub.add_argument(
                "--judge",
                action="append",
                required=True,
                help="backend/model of a judge (repeatable; bias probes the first one)",
            )

    args = parser.parse_args(argv)
    settings = get_settings()
    if args.command == "run":
        return _run_command(args, settings)
    if args.command == "compare":
        return _compare_command(args)
    if args.command == "report":
        return _report_command(args, settings)
    if args.command == "gate":
        return _gate_command(args, settings)
    if args.command == "calibration-set":
        return _calibration_set_command(args, settings)
    if args.command == "annotate":
        return _annotate_command(args, settings)
    if args.command == "bias":
        return _bias_command(args, settings)
    return _calibrate_command(args, settings)


if __name__ == "__main__":
    raise SystemExit(main())
