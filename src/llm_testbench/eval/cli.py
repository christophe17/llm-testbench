"""The harness from the command line: ``python -m llm_testbench.eval.cli <command>``.

- ``run``: run the arms of a suite (``config/eval_suites.toml``), print the comparison
  table, save every run to the history table when a database is configured, archive the
  full runs under ``data/results/runs/`` and say how each differs from the run it replaces;
- ``compare``: two archived arms of a suite, query by query;
- ``report``: the comparative HTML report, rebuilt from the archived runs;
- ``gate``: the regression gate, always in sample mode (pre-push hook, CI).

In sample mode (``LLM_TESTBENCH_SAMPLE=1``) nothing is archived: a sample run checks the
mechanics, it is not a number.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from psycopg import AsyncConnection, OperationalError

from llm_testbench.config import Settings, find_repo_root, get_settings, load_env_file
from llm_testbench.eval.compare import compare_runs, describe_difference
from llm_testbench.eval.gate import (
    BASELINE_PATH,
    GATE_SUITE,
    GateBaseline,
    check_gate,
    format_findings,
    gate_passes,
)
from llm_testbench.eval.report import write_report
from llm_testbench.eval.run_store import RunStore
from llm_testbench.eval.runs import RetrievalRun, format_runs, load_run, save_run
from llm_testbench.eval.suite import Suites, run_arm
from llm_testbench.ingest.store import PgVectorStore
from llm_testbench.llm.client import LLMClient

DEFAULT_SUITE = "retrieval-baseline"


def archive_path(results_dir: Path, suite: str, arm: str) -> Path:
    return results_dir / "runs" / suite / f"{arm}.json"


async def run_suite(
    suite_name: str,
    arm_names: list[str] | None,
    *,
    settings: Settings,
    results_dir: Path | None,
    record_history: bool = True,
    echo: bool = True,
) -> list[RetrievalRun]:
    suite = Suites.from_settings(settings).get(suite_name)
    arms = suite.select(arm_names)
    client = LLMClient.from_settings(settings)
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
            run = await run_arm(
                suite_name, suite, arm, settings=settings, client=client, store=store
            )
            runs.append(run)
            if history is not None:
                await history.save(run)
            if results_dir is not None and run.publishable:
                previous = archive_path(results_dir, suite_name, arm.name)
                if echo and previous.is_file():
                    sys.stderr.write(f"  {against_archive(run, load_run(previous))}\n")
                save_run(run, results_dir)
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


async def run_gate(settings: Settings, *, require_db: bool) -> tuple[list[RetrievalRun], list[str]]:
    """The gate suite, forced into sample mode whatever the environment says: it can
    neither download a dataset nor spend a cent. Returns the runs and the skipped arms."""
    sample = settings.model_copy(
        update={"sample": True, "fixtures_dir": find_repo_root() / "tests" / "fixtures"}
    )
    arms = Suites.from_settings(sample).get(GATE_SUITE).arms
    skipped: list[str] = []
    if not await database_reachable(sample.database_url):
        if require_db:
            raise SystemExit("evaluation gate: a database is required here and none answers")
        # A laptop with its cluster down still gets the arms that need no database; a
        # hook that fails whenever the cluster is off is a hook that gets bypassed.
        skipped = [arm.name for arm in arms if arm.retriever == "dense"]
        sample = sample.model_copy(update={"database_url": None})
    names = [arm.name for arm in arms if arm.name not in skipped]
    runs = await run_suite(
        GATE_SUITE, names, settings=sample, results_dir=None, record_history=False, echo=False
    )
    return runs, skipped


def _run_command(args: argparse.Namespace, settings: Settings) -> int:
    results_dir = None if args.no_archive else find_repo_root() / "data" / "results"
    runs = asyncio.run(run_suite(args.suite, args.arm, settings=settings, results_dir=results_dir))
    sys.stdout.write(format_runs(runs) + "\n")
    if not settings.database_url:
        sys.stderr.write("no LLM_TESTBENCH_DATABASE_URL: runs not saved to the history table\n")
    return 0


def _compare_command(args: argparse.Namespace) -> int:
    results_dir = find_repo_root() / "data" / "results"
    for arm in (args.candidate, args.baseline):
        if not archive_path(results_dir, args.suite, arm).is_file():
            raise SystemExit(f"no archived run for arm {arm!r}: make eval ARMS={arm}")
    candidate = load_run(archive_path(results_dir, args.suite, args.candidate))
    baseline = load_run(archive_path(results_dir, args.suite, args.baseline))
    sys.stdout.write(format_runs([baseline, candidate]) + "\n")
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

    args = parser.parse_args(argv)
    settings = get_settings()
    if args.command == "run":
        return _run_command(args, settings)
    if args.command == "compare":
        return _compare_command(args)
    if args.command == "report":
        return _report_command(args, settings)
    return _gate_command(args, settings)


if __name__ == "__main__":
    raise SystemExit(main())
