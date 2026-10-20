# llm-testbench

**Measured LLM testbench.** Every retrieval, generation and agentic technique implemented
here is measured on public datasets with annotated ground truth (BEIR, HotpotQA, SQuAD 2.0,
QASPER, Spider, BIRD…), and compared to the published scores in the literature. The system
is deployable and operated for real — API, Kubernetes, observability, costs — but its
selling point is the measurement, not the use case.

> 🚧 Work in progress: phase 1 (production skeleton) built, phase 2 (evaluation) to come.
> The master results table will appear from phase 2 on.

## What this testbench does not simulate

There are **no users and no real traffic**. Everything that assumes production — A/B
testing, canary, drift detection, feedback loop — will be demonstrated on a synthetic
traffic generator replaying the queries of the public datasets according to configurable
load profiles. This simulation captures neither the adversarial or out-of-distribution
behavior of real users, nor real seasonality, nor genuine human feedback. It is an
acknowledged limitation of the setup, not a detail.

Moreover, the public datasets used are probably present in the training data of the
evaluated models: contamination is treated as a measurement topic (phase 2), not ignored.

## Getting started

```bash
make setup          # uv sync + pre-commit hooks
make check          # lint + typecheck + offline tests
make notebooks-ci   # notebooks in sample mode (like the CI)
make k3d-up         # local k3d cluster + Postgres/pgvector
```

## Structure

See `CLAUDE.md` (working contract), `docs/roadmap/` (the phases), `STATE.md` (current state),
`docs/decisions.md` and `docs/adr/` (decisions),
`notebooks/` (one subfolder per phase; start with `notebooks/phase-0/00_guided_tour.ipynb`,
a guided tour of the architecture and the datasets), `docs/reading-order.md` (in which
order to read all of this, phase by phase).

## Data licenses

The code is under the MIT license. The datasets keep their own licenses — details verified
in `docs/datasets-verification-2026-08-26.md`. No data is redistributed in this repository
apart from tiny test fixtures; in particular, some datasets (FUNSD, ChartQA, DocVQA) carry
licenses that forbid or complicate redistribution.
