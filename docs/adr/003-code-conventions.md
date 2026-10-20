# ADR 003 — Code and tooling conventions

- **Date**: 2026-08-26
- **Status**: accepted; language clause superseded by 010

## Context

Frozen decisions from the brief (§4) to materialize as executable configuration, plus a few
trade-offs left open.

## Decisions

- **Python 3.12 exclusively** (`requires-python = ">=3.12,<3.13"`), managed by `uv`
  (versioned lockfile, `uv sync --frozen` in CI). Known exception: BFCL (phase 4)
  requires 3.10 → separate environment, ADR 001.
- **Package `llm_testbench`**, `src/` layout, `py.typed`. Prose in French, identifiers
  and code in English; docstrings in French because the first reader is the learner.
  *Superseded on 2026-10-20 by ADR 010: everything in English.*
- **ruff** (lint + format, line 100, rules E/W/F/I/UP/B/SIM/RUF/PT/T20); **mypy strict**
  on all of `src/` and `tests/`.
- **Offline tests by default**: the `network` marker isolates any test that downloads;
  CI only runs `-m "not network"`. Loaders accept a fixtures directory
  (`LLM_TESTBENCH_FIXTURES_DIR`) so that the same join logic runs on fixtures
  and real data — we do not test a mock of the logic, we replay the real logic
  on tiny data.
- **Sample mode**: `LLM_TESTBENCH_SAMPLE=1` + `sampled=True` carried by the data
  itself. Any number coming from a `sampled` dataset is unpublishable, by construction.
- **GitHub Actions CI without secrets**: lint, typecheck, offline tests, notebooks via
  nbmake in sample mode on fixtures. Full runs (published numbers)
  are manual and archived.
- **pre-commit**: file hooks + ruff + mypy. `check-added-large-files` at 2 MB to
  block an accidental data commit.

## Consequences

`make check` reproduces CI locally. The cost: mypy strict requires annotations
everywhere, including in tests — accepted, it is the level expected of production code.
