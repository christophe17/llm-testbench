# PHASE 0 — Foundations (week 1)

**Status: done** (PR #1 merged on 2026-08-26; closing documented on 2026-09-03).

Repo, tooling, CI (lint, typecheck, tests, notebook execution), local cluster,
Postgres/pgvector.

Before starting: blocking questions (API keys available, accepted monthly budget, actual weekly
time), then checking the availability, the size and the license of
each dataset, and proposing the smallest possible starter subset.
**In phase 0 we build only the loading interface and ONE reference loader** — a
single dataset, the smallest. The other loaders arrive with the phases that need them.

**Notebook 0**: guided tour of the target architecture and of what each module will do. Plus:
what each dataset looks like, what it measures, what it does not measure.

## What was decided

- API keys: OpenAI, Anthropic, OpenRouter; Mistral and others via OpenRouter as long as there
  is no dedicated key. No budget cap a priori. No schedule.
- Reference loader: BEIR/SciFact (ADR 001, ADR 004).
- Langfuse and AWS cloud modules postponed to phase 1; in phase 0, Terraform bootstrap only
  (state bucket + 55 USD budget with alerts) (ADR 002).
- Offline CI without secrets, notebooks in sample mode (ADR 003).

## First action of the brief (historical, done on 2026-08-26)

Write the brief in `CLAUDE.md`, create `STATE.md` and `JOURNAL.md`, flag the problems of the
plan, verify the datasets, ask the blocking questions, then wait for
`GO PHASE 0`.
