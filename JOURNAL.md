# JOURNAL

> Dated history of the project, kept as work goes. One entry per significant work session.
>
> Entry format:
>
> ```
> ## YYYY-MM-DD — short title
> **Context**: where we were.
> **Done**: what was built, measured or decided (with numbers when there are any).
> **Incidents / surprises**: what broke, what contradicted an assumption — raw material
> for the phase 8 interview stories, to be recorded on the spot.
> **Next**: the next concrete step.
> ```

## 2026-08-26 — Kickoff: brief, steering, dataset verification

**Context**: project restarted from scratch on the `phase-0` branch (a first draft of phase 0 existed in the git history; the working tree was deliberately emptied to start over from the brief).

**Done**: mission brief consolidated in `CLAUDE.md`; `STATE.md` and `JOURNAL.md` created; web verification (exact name, version, license, size, retrieval method) of each dataset in the table of section 4 of the brief; answers to the blocking questions obtained (OpenAI/Anthropic/OpenRouter keys, budget according to real need, no calendar).

**Incidents / surprises**: —

**Next**: validation of the starting subset and `GO PHASE 0`.

## 2026-08-26 — Phase 0 built: tooling, SciFact loader, CI, k3d, bootstrap

**Context**: `GO PHASE 0` received; calls validated — package `llm_testbench`,
Langfuse + cloud modules postponed to phase 1, AWS bootstrap alone with a ~EUR 50 budget.

**Done**: complete tooling (uv/ruff/mypy strict/pytest/pre-commit); loading interface
with referential integrity validation and a `sampled` flag carried by the data;
BEIR/SciFact loader (join of 3 HF Parquet repositories), 13 offline tests + network
smoke test; offline CI (notebook in sample mode via nbmake); k3d + Postgres/pgvector
verified end to end (`vector` extension 0.8.6 active); bootstrap Terraform written and
validated, not applied (AWS account to be created); notebook 0 run in both modes,
automatic check of the volumes against the BEIR paper (5,183 docs, 300 test queries —
compliant).

**Incidents / surprises**:
- The user Jupyter kernelspec `python3` pointed to a Homebrew Python 3.10 and masked the
  project venv: the notebook passed under `uv run` but failed under nbmake
  (`ModuleNotFoundError`). Fix: a dedicated `llm-testbench` kernel registered by
  `make setup` and by the CI. Lesson: a notebook that "works on my machine" may run in
  another interpreter than the one you think.
- Local k3d 5.4.6 (2022, k3s 1.24) rejected the `v1alpha5` apiVersion; an `llm-testbench`
  cluster inherited from the first draft was still lying around and `kubectl apply`
  targeted it without warning. Cleanup, k3d upgraded to 5.9.0, clean recreation. Lesson:
  always check `kubectl config current-context` before applying.
- SciFact qrels ids arrive typed `int` on the HF side while the corpus ids are `str`:
  without a systematic cast, the join fails silently. This is exactly the kind of bug
  that integrity validation at construction catches.

**Next**: review of the phase 0 PR; `make bootstrap-apply` when the AWS account
exists; `GO PHASE 1`.

## 2026-08-26 — Notebook 0 rewritten after feedback: "I'm completely lost"

**Context**: first version of notebook 0 rejected at review — it exposed the code of
`src/` assuming all the IR/LLM vocabulary was known (retrieval, qrels, splits, BM25,
nDCG), whereas that vocabulary is precisely what the project must teach.

**Done**: complete rewrite in 38 cells, with an imposed progression: concrete problem →
notions on a five-line toy example → real data explored → only then the code of `src/`
read block by block → tour of the testbench → experiments → glossary of 22 terms. Each
term is defined at its first appearance. Rule set in stone in `CLAUDE.md` §8 for all
upcoming notebooks.

**Incidents / surprises**: the brief's contract ("guided reading of the real code") was
followed to the letter but missed in substance: showing the real code does not exempt you
from building the concepts first. The right order turned out to be: see the data first,
read the code next — the reverse of v1.

**Next**: review of the new version of the notebook.

## 2026-08-27 — Market audit and roadmap extension (8 → 10 phases)

**Context**: question asked — is the roadmap calibrated for a remote AI Engineer position
in France? Web check against 2026 job offers and recruitment analyses.

**Done**: core of the roadmap confirmed (eval, agents, MCP, observability, cost, vLLM —
"evaluation literacy" is cited as the top hiring signal). Four gaps identified and
integrated: GraphRAG (phase 3, behind a flag, an acknowledged candidate for measured
removal), agent memory (4.10 + notebook 7), voice agents (new phase 9), browser/
computer use (new phase 10, optional, GO/NO-GO at the end of phase 9). The framework
landscape (LangChain, LlamaIndex, CrewAI, smolagents, OpenAI Agents SDK) and A2A covered
as knowledge in the notebooks, never as implementation. Minimal chat UI added at the end
of phase 5. Decisions recorded: public repo confirmed; 2 interested clients → client
deployments will be separate repos ("real prod" portfolio), the testbench remains the
laboratory — the "never a second project" rule holds, extensions plug into the single
system to reuse the harness, infra and observability.

**Incidents / surprises**: market watch point — full remote is a minority in this job in
France (even Mistral expects presence in Paris); targeting remote narrows the funnel and
increases the weight of the measurement/portfolio differentiator.

**Next**: unchanged — review of the phase 0 PR, then `GO PHASE 1`.

## 2026-08-27 — Revision: frameworks move to measured comparison

**Context**: objection raised against the morning's decision ("frameworks as knowledge
only") — an offer that requires LangGraph/CrewAI goes through an ATS filter before
reaching a human; a keyword missing from the CV can be eliminatory at screening, even if
the interview would be won on concepts.

**Done**: decision revised. Phase 4.1: the same reference agent ported to smolagents,
OpenAI Agents SDK and CrewAI, measured on the same harness (accuracy, tokens, latency,
lines of code, ~1 day per framework) — the ports are benchmark deliverables,
`src/` keeps a single production implementation (in-house + LangGraph). Phase 3:
our pipeline compared to out-of-the-box LlamaIndex on the same BEIR dataset
("ours first, then the comparison" pattern, already recorded for Ragas/promptfoo in phase 2).
A2A remains under discussion. Expected benefit: honestly earned CV keywords + a
measured framework comparison that almost nobody publishes.

**Incidents / surprises**: —

**Next**: unchanged — review of the phase 0 PR, then `GO PHASE 1`.

## 2026-08-31 — Amendment: phase 5B "The bridge", classic ML vs LLM

**Context**: request for a short phase after phase 5 to measure, with the existing
harness, the classic ML / LLM / hybrid trade-off — the deliverable nobody brings to an
interview. Apparent conflict with the §6 "no prediction" rule.

**Done**: phase 5B written and inserted between 5 and 6 in `CLAUDE.md` (numbering
kept, "B" = inserted after the fact); §6 rule reworded: a named, unique exception,
three locks (no other prediction task, no score chasing, `classic/` module
never exposed by the API). ADR 005 with web verification of the candidate datasets. Three
corrections made to the initial statement: (1) the "reference GBM" arm splits into
text-ignored and text-as-n-grams — the literature (Shi et al. 2021) shows that the classic
hybrid (AUC 0.968) beats the hybrid with LLM embeddings (0.926), so without this arm the
table would flatter the LLM; (2) TabLLM is comparable only for its zero-shot, its few-shot
is fine-tuning; (3) the expectation "small quality gap" on text will probably not hold on
77 fine-grained intents — declared before measurement, published as is.

**Incidents / surprises**: EMSCAD's original site (University of the Aegean) is dead — it
returns a generic hosting page; the original license of the recommended tabular dataset
is therefore no longer verifiable at the source, only the benchmark's copy (CC BY-NC-SA) is.
`PolyAI/banking77` on HF is still script-based (broken with `datasets` ≥ 3), a Parquet PR
has been open since August 2025 with no answer from the maintainers: plan for a mirror or
the GitHub CSV.

**Next**: decide on the two datasets of phase 5B (not blocking before that phase);
otherwise unchanged — review of the phase 0 PR, then `GO PHASE 1`.

## 2026-08-31 — Phase 5B datasets decided

**Context**: ADR 005 recommendation submitted.

**Done**: selected `fake_job_postings2` (tabular with free text, EMSCAD via the AutoGluon
multimodal benchmark) and Banking77 (text classification, 77 intents). Substitutes
kept in the ADR: `women_clothing_review`, MASSIVE fr-FR. ADR 005 accepted without reservation.

**Incidents / surprises**: —

**Next**: unchanged — review of the phase 0 PR, then `GO PHASE 1`.

## 2026-09-01 — Question: is the data pipeline the natural extension?

**Context**: question asked while rereading the brief — would a "data pipeline" phase
be the logical continuation of the roadmap?

**Done**: negative answer, recorded, no change to the roadmap. Arguments:
(1) phase 3 is already an operated data pipeline (Dagster, partitions, idempotence,
lineage, Pandera, incremental reindexing) with a justification specific to the testbench —
the experiment matrix, not freshness; (2) a pipeline in the data engineering sense
(Kafka, Spark, dbt, CDC) exists for data that moves — the testbench has neither a live
source nor traffic, it would reintroduce the "live corpus" logic removed by the pivot, a
typical case of the "floating block" of the §6 consistency audit; (3) outside the
positioning — data engineering is a neighboring job, the market audit of 2026-08-27 did
not retain it; (4) real data pipelines will have their place in the separate client repos.
Two "data" extensions judged legitimate: the LLMOps data loop (traces →
judge → curation → golden set / LoRA set, linking phases 2, 5 and 6, on synthetic
traces to be declared as such), noted as a post-phase-10 candidate in `STATE.md`;
and document parsing at scale (Docling / unstructured / marker on the hard-to-parse
in-house corpus, measured impact on retrieval), which belongs to notebook 2 of
phase 3 rather than to a new phase. The phrase "data pipeline" is already legitimate
in the README and the CV thanks to phase 3: to be phrased that way in phase 8.

**Incidents / surprises**: —

**Next**: unchanged — review of the phase 0 PR, then `GO PHASE 1`.

## 2026-09-03 — Phase 0 closing: notebook reviewed, local environment repaired

**Context**: notebook 0 reviewed in full (teaching version rewritten on 2026-08-26); PR #1
merged into `main` since 2026-08-27; docs amendments (phase 5B, journal of 2026-09-01) still
uncommitted.

**Done**: complete local check before closing — ruff, mypy strict, 13 offline tests,
notebook 0 run in sample mode by nbmake — all green after repairing the environment
(below). Phase 0 declared done, debrief delivered. The protocol stops there until
`GO PHASE 1`.

**Incidents / surprises**: the repository was moved from `~/Sites/` to `~/Roadmaps/`. The
venv console scripts (`.venv/bin/pytest`, `mypy`), the `llm-testbench` Jupyter kernel and the
pre-commit hook still carried the old absolute path (shebang / `kernel.json` /
`INSTALL_PYTHON`). Misleading symptoms: `uv sync --frozen` answered "Audited 141
packages" (nothing to do), ruff and mypy passed, but `uv run pytest` failed on
`ModuleNotFoundError: llm_testbench` and an unknown `--nbmake` — because the `pytest` that
ran was the conda base one (8.4.1, on PATH), not the venv one (9.1.1).
Decisive diagnosis: `head -1 .venv/bin/pytest`. Fix: `uv sync --reinstall`,
kernel re-registration (`make setup`), `pre-commit install`. Lesson, same family as
the kernelspec incident of 2026-08-26: a tool that "passes" does not prove that it runs in the
interpreter you think, and `uv sync` does not check shebangs. Hardening:
the Makefile now invokes `python -m pytest` (goes through the venv's `python` link,
insensitive to relocation) instead of the `pytest` console script. One stale path remains,
purely cosmetic, in a versioned output of notebook 0 (displayed root) — it will be
refreshed at the next full run.

**Next**: docs PR for the uncommitted amendments; `GO PHASE 1`.

## 2026-09-03 — Phase 1: production skeleton built in one session

**Context**: `GO PHASE 1` received that morning, after the phase 0 closing. Plan validated
with four calls (OpenRouter as a breadth backend only, data governance from
phase 1 on, teaching infra guides, QASPER + embeddings trio).

**Done**: complete LLM layer (ADR 006), sources/ingestion/pgvector (ADR 007), JSON + SSE API,
image + Helm chart + Tilt verified on k3d, Terraform `envs/dev` validated, Langfuse v4 on k3d
with working OTLP, 8 infra guides out of 9, notebook 1 run in CI. 151 offline tests,
6 on a database. Details in `STATE.md`.

**Incidents / surprises**:
- **Two versions of the same linter contradict each other.** The pre-commit hook pinned
  ruff 0.6.9, the project uses the version resolved by uv; a test style rule (PT012) passed
  in one and blocked in the other. Fix: the hooks go through `uv run ruff`; `make lint`
  also covers the notebooks, like the hook. Same family as the morning's moved venv: a
  "green" tool proves nothing about the tool that actually runs.
- **`$path` in zsh is `PATH`.** A `for path in …` loop wiped the shell's PATH: "curl:
  command not found". Twenty minutes of diagnosis for a badly named variable.
- **Current Claude models refuse `temperature`.** Checked in the API reference: the
  Anthropic provider ignores `temperature` and `seed` (otherwise 400). Phase 5B's
  "temperature 0 for determinism" will be measured another way. Recorded in notebook 1.
- **The Langfuse 2.x chart requires a ClickHouse operator** (CRD, three keepers): too heavy
  for the local "bare minimum". Workaround: single-node ClickHouse in a 60-line
  StatefulSet, the chart in "external ClickHouse" mode. Then **Langfuse v4 is in
  `events_only` mode**: the `/api/public/traces` and `/observations` endpoints return 404;
  the OTLP spans are indeed in ClickHouse (`events_core`), with all our attributes, and
  Langfuse recomputes the cost ($0.00187, identical to ours — a free cross-check). The
  worker, started before the migrations finished, had also left errors: restarted.
- **`helm --wait` times out on a readiness probe that refuses**: it is not a bug, it is
  `/readyz` saying "index missing". Documented (guides 01 and 06) rather than worked around.
- **A pipe masks a failure** (`make check | tail` under `set -e`): a commit tried to go
  out with mypy red, the hook stopped it. `set -o pipefail` from now on in command chains.
- **The chunking tests had never run**: every `make check` stopped at lint before
  pytest. Two wrong expectations in the tests, fixed; the chunker was right.

**Next**: guide 07, notebook 2 (chunking + measured embeddings), full run with keys,
bootstrap and `infra-up` by Christophe, phase 1 PR.

## 2026-09-03 — Phase 1: notebook 2, first measurement, end of construction

**Context**: continuation of the session; guide 07, notebook 2 and the embeddings
comparison remained.

**Done**: guide 07 (Langfuse v4, OTLP proven down to ClickHouse, read back through the v2 API);
`eval/embeddings_bench.py` module (mteb + adapter on `LLMClient.embed`); notebook 2
run on the local database; **first measurement of the testbench**: bge-base-en-v1.5 0.740
nDCG@10 on SciFact — **equal to the number published on its model card (0.7404)** — and
all-MiniLM-L6-v2 0.645, **below BM25 (0.665)**. The model of every tutorial loses to a
keyword search on this dataset: the justification for phase 3's hybrid search, quantified
before it even exists. Postgres as a service in the CI for the `db` tests and notebook 2.

**Incidents / surprises**:
- **Feature hashing and collisions**: the 32-dimension "hashed bag of words" embedder gave
  a zero cosine between two sentences that share three words — two words landing in the
  same bucket with opposite signs. At 256 dimensions the phenomenon persists (0.5 instead
  of 0.75) on five words; the test now checks the property (shared ≫ disjoint,
  identical = 1) at 1,024 dimensions rather than a value. A good illustration for the
  notebook: an embedding is a projection, and a projection loses information.
- **A cache that lies about time**: mteb caches its results; the first table
  showed 2 s of "indexing". The module forces re-evaluation so that the duration column
  is a real encoding time (20 s and 120 s on an M1 Pro).
- **A regex that was not one**: a heredoc doubled a backslash… then did not;
  the real cause was the collision above. Diagnosing by observing (printing the
  vectors) cost less than guessing.
- **Langfuse v4 events_only** (see the previous entry): reading back goes through
  `/api/public/v2/observations`; recorded in guide 07.
- **The CI caught what my workstation masked.** On a fresh database, the psycopg pool
  failed ("vector type not found"): each connection registers the `vector` type at its
  creation, before `ensure_schema` could create the extension. Locally, the phase 0
  pgvector-init job had already created it: 6 green tests, an invisible bug. Fix: the
  schema goes through a raw connection in `open()`, before the pool; reproduced on a blank
  k3d database (`CREATE DATABASE ci_fresh`), fixed, CI green. Lesson: a dev environment
  with history is not a fresh environment; CI with a disposable Postgres service is.
  First staging of a green CI. The CI's mypy had also rejected a `type: ignore` that my
  workstation, with `mteb` installed, made necessary — same family.

**Next**: `phase-1` PR; Christophe's actions: keys in `.env`, full runs,
AWS bootstrap then `make infra-up` / `make deploy` (guides 00→05); then `GO PHASE 2`.

## 2026-10-15 — The word "pipeline": no separate roadmap, three amendments

**Context**: question asked while looking at the whole portfolio (the testbench plus
four neighboring projects, specified or in progress, two of them without code) — is the
"pipeline side" of AI Engineer job offers covered, or is a dedicated roadmap needed?
The question of 2026-09-01 taken up again, this time with the neighboring projects on the table.

**Done**: negative answer confirmed, and the brief amended. Analysis: the word "pipeline"
covers four things in job offers — RAG pipeline (phases 1 and 3), orchestrated data pipeline
(phase 3, Dagster, partitions, lineage, Pandera), asynchronous event-driven pipeline
(queue, worker, DLQ) and training platform (reproducibility, versioning, DDP,
export). The last two are carried by neighboring projects that do not have a single line of
code and whose horizon extends beyond that of the permanent-position search: the testbench
does not count on them. Kafka, dbt and streaming stay out of scope (data engineering, a
neighboring job). Three weaknesses fixed by amendment: (1) phase 3's Dagster block was a
passing line with no ADR or notebook, whereas it is the deliverable that answers the
keyword — it becomes a named deliverable with an ADR, a master table row and notebook 5;
(2) phase 5's asynchronous judge and feedback imposed no form — they go through a real
queue and a worker, which gives an event-driven pipeline coded in this repository whatever
happens elsewhere; (3) no run manifest for the 5B and 6 trainings — required from now on,
with no additional tool. Written into `CLAUDE.md` (§5 phases 3, 5, 5B, 6; §6; §8) and
`STATE.md`.

**Incidents / surprises**: the job-offer analysis of 2026-08-27 that motivated the
frameworks extension is archived nowhere; the reasoning on the meaning of the word
"pipeline" rests on general knowledge of 2026 job offers, not on a corpus that was reread.
To be checked against real job offers at phase 8.

**Next**: unchanged — `phase-1` PR, Christophe's actions (keys, full runs,
AWS bootstrap), then `GO PHASE 2`. The amendments apply to the plans of phases 3, 5,
5B and 6.

## 2026-10-16 — Brief restructured, everything on `main`

**Context**: `CLAUDE.md` was 56 KB (~15,000 tokens) loaded at every session and in
every subagent, roadmap of phases 0 to 10 included; amendments piled up in §8 instead
of correcting the text (example: §1 still targeted the permanent AI Engineer position,
which decision PD-8 relegates to a fallback). Three open branches (`phase-0` merged,
`phase-1` and the docs branch pending since 2026-09-03).

**Done**: `CLAUDE.md` reduced to the working contract (§1–4, §6, numbering kept for the
references from the code); roadmap in `docs/roadmap/` (overview + datasets table, one file
per phase, amendments integrated into the text); §8 moved as is into `docs/decisions.md`.
PR #3 merged (it contained #2), branches deleted locally and on GitHub; from now on
everything on `main` (ADR 008). Phase 2.7 reworded accordingly: a `pre-push` hook + red CI
instead of a blocked PR.

**Incidents / surprises**: PR #3 was merged without a formal review by Christophe —
the phase 1 review now happens on `main`. Working without PRs removes the only
mechanism that *blocked* a regression: to be presented honestly in interviews (ADR 008).

**Next**: unchanged — Christophe's actions (keys, full runs, AWS bootstrap), then
`GO PHASE 2`.

## 2026-10-19 — Notebooks organized by phase

**Context**: `notebooks/` was flat, numbered in a global sequence (00 = phase 0, 01 and
02 = phase 1). The notebook → phase link could not be read anywhere in the naming, and the
roadmap already reserved numbers ("notebook 5" for Dagster) that only `STATE.md` tied to a
phase.

**Done**: one subfolder per phase, `notebooks/phase-N/NN_slug.ipynb`, files moved with
`git mv` without renaming. The Makefile and the CI pass the whole `notebooks/` folder to
nbmake: any added notebook is run by the CI without touching the list. The three notebooks
re-run in sample mode (notebook 2 on a disposable pgvector container, the k3d cluster being
off).

**Incidents / surprises**: notebooks 1 and 2 looked for `.env` in `Path.cwd().parent`,
that is, the root only as long as they lived in `notebooks/`. One level lower,
the file would no longer have been found and the "real provider" section would have been
disabled without an error — the CI, in sample mode, would never have seen it. They now
anchor on `find_repo_root()` like their other paths. Lesson: a path relative to the current
directory in a notebook is a hidden dependency on the file's location.

**Next**: unchanged — Christophe's actions (keys, full runs, AWS bootstrap), then
`GO PHASE 2`.

## 2026-10-19 — Resumption: testbench audit, a single environment, OIDC deployment, AWS services rule

**Context**: project set aside for a month. Christophe asks for three things: validate that the
testbench serves the overall roadmap (`~/Roadmaps/program`) and the search for freelance
engagements, audit what has been generated, and judge the choice of Kubernetes against
Christophe's need to build AWS skills without a bad infra decision. The program changed that
very morning (PD-18: sherpapier frozen, this testbench is the proof for engagements).

**Done**: audit delivered (`docs/decisions.md`, first line of the day) — both objectives
hold, EKS confirmed, eight corrections. Then, on Christophe's go-ahead: `prod` removed from
the brief; CV sent back to the program and the number of years removed from §1;
`docs/aws-competences.md` deleted; doc rot fixed (Terraform README, guides index, README
banner); **ADR 009**; **deployment via GitHub Actions and OIDC** (bootstrap `github.tf`,
access entry in `envs/dev`, `deploy.yml` on an arm64 runner, `make deploy-trigger`, guide 09);
**database URL composed in the cluster** by an External Secrets template — the RDS password
no longer goes through the Terraform state; **AWS services entry rule** in `CLAUDE.md` §4
and its first applications in phases 3 to 7; Claude 5.5 generation by default and the
price table of the day. Verified: `terraform validate` on both modules, `helm lint` and
rendering of the `ExternalSecret` with the `database.*` values, `make check` (155 tests,
mypy strict), notebooks 1 and 2 re-run in sample mode on a disposable pgvector.

**Incidents / surprises**:
- **A parallel session was reorganizing the notebooks** (`notebooks/phase-N/`) during the
  audit: `FileNotFoundError` on a path read ten minutes earlier. Its work was complete and
  recorded; committed separately, before mine, by isolating its Makefile block from mine with
  a partial patch. Lesson: two sessions on the same repository means `git status` before
  every write, and never a global commit.
- **An editing script stopped by its own safeguard**: an anchor copied without its `**`
  no longer matched; the assertion prevented a partial edit of five guides. The cost
  of an exact anchor is lower than that of a half-modified file.
- **Restricting the EKS endpoint to one IP and deploying from GitHub are mutually exclusive**
  without a runner in the VPC or a pull mode: the audit's "hygiene" correction gave way to
  the pipeline, and the decision is written down (ADR 009) rather than suffered.
- **Haiku 5.5 has no published cache price** in the reference that was captured: the table
  leaves it absent, and `cost_usd` returns `None` on a cached call — as intended. The
  notebook 1 cost table broke on it: the cell handled this `None` for the "savings" column
  and not for the "1 call (cache)" column. Fixed: it displays "unknown". The "never
  an estimate" rule held even in the display, and the notebook demonstrates it.
- **The GPU quota code cannot be verified** outside an account: `STATE.md` has the code
  looked up by its name rather than hard-coding it.

**Next**: Christophe's actions (`STATE.md`) — review the day's commits, keys, full
runs, bootstrap (eight resources), GitHub variable, GPU quota request — then
`GO PHASE 2`.

## 2026-10-20 — Testbench reading order, GPU quota request

**Context**: Christophe resumes the built phase 1 and asks in which order to read the
files, then for the list to be written out up to phase 10, then for the GPU quota requests
of `STATE.md` to be sent.

**Done**: `docs/reading-order.md` (16 blocks: phases 0 and 1 down to the module, phases 2 to 10
on the deliverables named by the roadmap, to be completed at each phase closing), references in
`README.md` and `STATE.md`. GPU quota: identity verified (account 749020018778, user
`christophe`), both G and VT quotas at 0 in eu-west-3, no request pending, g6.xlarge and
g6.2xlarge offered in the region. Spot request (`L-3819A6DF`) sent at 8 vCPU at 10:51;
On-Demand request (`L-DB2E81BA`) sent by Christophe at 10:54; both in `CASE_OPENED`.

**Incidents / surprises**:
- **The On-Demand request (`L-DB2E81BA`) was refused by the Claude session's safeguard**
  ("real transaction"), whereas the Spot request, of strictly the same nature, went through
  right after. No identical retry: the exact command was put in `STATE.md`
  and Christophe ran it by hand three minutes later. Lesson: two identical calls
  can be judged differently by a classifier; record the state after each
  real action, not at the end.
- Two Standard quota requests (On-Demand and Spot, 32 vCPU) dated 2026-09-03 are
  `CASE_CLOSED` in the history, a status that does not say whether they were granted;
  verified: both quotas are at 32 vCPU, `make infra-up` (guide 03) is not blocked.

**Next**: Christophe's actions (`STATE.md`); then `GO PHASE 2`.

## 2026-10-20 — The repository goes entirely English

**Context**: Christophe asks for everything to be translated into English: no French in the
project. Until then, prose, docstrings and notebooks were in French by rule (ADR 003,
`CLAUDE.md` §2.B.5), and the program's PD-5 exempted this repository.

**Done**: work of the parallel session of the day committed separately first (`ceab409`);
18 French-named files renamed with their in-repository references (`e568501`); then the whole
content translated in parallel batches with a shared glossary: brief, roadmap, ADRs,
`docs/decisions.md`, infra guides, Terraform/Helm/k8s comments and descriptions, Makefile,
workflows, configuration notes, `src/` (docstrings, comments, error and governance messages),
tests and their data, prompts (new versions), the three notebooks. ADR 010, decision line,
ADR 003 and the 2026-10-16 decision annotated as superseded; the 2026-09-03 phase 1 plan
decision on deployment annotated (superseded by ADR 009). Verification: `make check` green
(155 passed), the 6 `db` tests green on a throwaway pgvector, the three notebooks re-executed
in sample mode with no error, no French left (accented characters and French function words
over every tracked file), no broken relative link.

**Incidents / surprises**:
- Test data was not translatable word for word everywhere: the toy embedders key on words
  (`capital`, `recipe`, `weather` replace `capitale`, `recette`, `météo`), the chunking test
  depends on paragraph lengths (longest paragraph now 318 characters, the test checks the same
  property), and the refusal test no longer exercises accent stripping since the sentinel has
  no accent.
- Translated Terraform `description` arguments show up at the next plan: in-place updates
  (bootstrap IAM role, ECR lifecycle rule, Secrets Manager secret), and a **replacement** of
  the RDS security group if `envs/dev` were up during the apply — it is down, a fresh
  `make infra-up` sees no difference.
- Two miscounts in the guides fixed along the way (guide 09 "three differences" for five
  items, guide 08 "three columns" for four); `pyproject.toml` no longer allows « » as
  confusables.

**Next**: update PD-5 in the program (`STATE.md`, decisions awaiting a call); Christophe's
actions (`STATE.md`); then `GO PHASE 2`.

## 2026-10-26 — `.env` had two half-readers

**Trigger**: `make ingest-scifact` with a filled `.env` stopped on
`MissingCredentialsError: OPENAI_API_KEY missing`, after finding the database URL in the same
file.

**Cause**: pydantic-settings read `.env` for the `LLM_TESTBENCH_*` fields only; the provider
keys are plain environment variables, read by the backend registry at call time and never
stored (ADR 006), and nothing exported them. Guide 01 compensated with a
`set -a; source .env; set +a` line before the ingestion, the two phase 1 notebooks with an
inline loop: three partial answers to one question.

**Done**: `load_env_file()` in `config.py` (comments, `export`, quotes, empty values skipped,
the environment wins unless `override`, no-op without file or repository root), called by the
three entry points: `ingest.cli`, `embeddings_bench`, and `create_app()` when the settings come
from the environment. `Settings` no longer reads `.env` itself: one file, one reader. The
uvicorn target `main:app` is now built on first access (module `__getattr__`, PEP 562) instead
of at import; importing the module from the tests used to build an app from the developer's
`.env`, which configured a trace exporter towards a Langfuse that was not running and, with the
new loader, would have exported the keys into the test process (the 6 `db` tests silently ran
against the local database for that reason). Tests in `tests/test_config.py`; `.env.example`
and guide 01 updated. Verified: `make check` green (159 passed, 6 `db` skipped), then the
ingestion end to end — 5,183 documents, 10,453 chunks embedded in 164 calls, 1.67 M tokens,
$0.033, 194 s; the 32 documents and 7 chunks already stored by the failed run and by a
3-document trial were not redone (ADR 007 idempotence).

**Left out**: the notebooks' inline `.env` loop still duplicates `load_env_file()` (contract
§2.B.1: the notebook implements nothing); to replace with an import at the next re-execution.
`make notebooks-ci` not rerun: the notebooks never relied on pydantic's `env_file` (their
working directory is not the repository root), so the change does not reach them.

**Follow-up, same day — readiness was a snapshot.** After the ingestion, the API pods under
Tilt kept answering `/readyz` 503 "index missing": the lifespan looked the index up once at
start-up (16:04Z, before the registry had the row) and nothing re-checked it, so both pods
stayed 0/1 and the rollout stuck with two ReplicaSets, the new pod never becoming ready.
Guide 01 step 5 promised readiness right after `make ingest-scifact`, without a restart. Now
the state carries a `refresh()` closure (one `SELECT` on the registry under an `asyncio.Lock`)
that `/readyz` and the service accessor call while not ready; once ready, no query. Offline
test with a stand-in registry (`test_readiness_recovers_when_the_index_appears`), `make check`
green (160 passed), local uvicorn smoke test plain and `--reload` against the k3d database:
`/readyz` ready at first probe. Observation for the Tilt work in progress: the live update had
synced the morning's edits into the `--reload` pod, but uvicorn logged no reload.

**Follow-up, same day — the cluster Secret carried the laptop's settings.** The next API pod
under Tilt crashed at start-up: `connection refused` on `localhost:5432`. `make k8s-secrets`
built the API `Secret` from every line of `.env`, so the laptop's `LLM_TESTBENCH_DATABASE_URL`
and Langfuse endpoint (both `localhost`) reached the pod, and the deployment lists the `Secret`
after the `ConfigMap`, so they won over the in-cluster values. The 16:04Z pods had only worked
because they started before the (optional) `Secret` existed, hence on the `ConfigMap` alone and
without API keys. The target now keeps the credential lines only (`grep -v '^LLM_TESTBENCH_'`,
piped into `--from-env-file=/dev/stdin`); guide 01 explains why. Applied to the cluster and the
pod replaced: it reaches `postgres.llm-testbench:5432`, `/healthz` 200, `/readyz` 503 "index
missing", correct since the namespace recreation of ~16:30Z took the PVC and the ingestion with
it; ingestion relaunched. Not touched: guide 06 still says the `Secret` is created "from
`.env`" (true but imprecise; the file is being edited in the parallel session).

## 2026-11-02 — The title never reached the embedding model

**Trigger**: a reading question on `make ingest-scifact` — one section per document? Yes:
`scifact_documents` wraps each BEIR abstract as a single untitled section and puts the paper
title in `ParsedDocument.title`. Checked on the cached corpus: 5,183 documents, 5,183 single
sections; median abstract 1,330 characters against a 1,000-character chunk, so 4,051
documents become two chunks or more.

**Found**: the pipeline embedded `chunk.text` and nothing else. The title was stored in
`documents` and shown in citations, never vectorized. BEIR and MTEB embed
`title + " " + text` — `mteb` does it itself for every retrieval corpus
(`_create_dataloaders.py`), so `make bench-embeddings` was already right — and the index was
not comparable to the published scores, for a reason unrelated to the model. No ADR, no
decision line: an omission, not a choice.

**Done**: `EmbeddingInput` in `ingest/chunking.py`, the chunk as the model sees it, built by
the pipeline from the document and the chunk; `Chunk`, the `chunks` table and the offsets are
untouched. The store's `missing_embeddings` / `add_embeddings` take it and key the vector on
the hash of the embedded text: the SciFact index of 2026-10-26 (title-less vectors, same chunk
hashes) is recomputed at the next run instead of being silently kept, and a retitled document
is embedded again. Tests: two offline on `EmbeddingInput`; the `db` tests assert what the fake
embedder received and the retitle path. ADR 007 and `docs/decisions.md` amended.

**Left out**: notebook 2 — its `inspect.getsource` cell shows the old pipeline until its next
execution, and the file is being edited by another session. The SciFact re-ingestion and the
before/after retrieval number wait for the phase 2 harness (nDCG@10 on our index, not mteb's).

## 2026-11-02 — Generated UML rejected, curated diagrams with a drift test

**Trigger**: "is there a tool that generates visuals of the classes from the code?". pyreverse
(pylint) was tried on `src/`: one Mermaid diagram per subpackage, 63 classes for `llm`, modules
drawn as empty boxes, flat module names colliding across subpackages (`eval/types`,
`llm/types`), and no edge between the providers and the `LLMProvider` protocol, since
structural typing is invisible to an inheritance scan. Verdict at first read: unreadable, not
professional. No VS Code extension does better in 2026; the polished generated view is
PyCharm Professional's, and it would still be an inventory.

**Done**: `docs/diagrams/`, eleven hand-drawn Mermaid class diagrams, one per concept, 7 to 12
classes each, with a README on the notation and an index; `tests/test_diagrams.py` parses every
block and checks the drawn classes, the listed members, the relation endpoints and the source
paths against the AST of `src/` (13 tests, offline); links from the guided reading of notebooks
01 and 02 and from `docs/reading-order.md`; `make uml-inventory` keeps pyreverse as the author's
raw inventory in the ignored `build/`. All eleven blocks parsed and rendered with Mermaid 11.4.1
before being kept. Decision line in `docs/decisions.md`.

**Incidents / surprises**: pylint 4 draws fewer relations than pylint 3.3 (composition becomes
a plain association), one more reason not to depend on a generator's output. `uv add` and
`uv remove` resync `.venv` exactly and uninstalled the `bench` group (torch, transformers);
restored with `uv sync --group bench`. `uv pip` without an activated venv inspects the Anaconda
Python, not `.venv`.

**Next**: one diagram per new concept at each phase, written before the notebook's guided
reading; the test keeps them honest.

## 2026-11-04 — Side notebook 2b: MTEB crash course

**Trigger**: "a side notebook, a kind of crash course for MTEB, just to understand what's needed
in this roadmap". MTEB sits in the roadmap three times — the phase 1 model comparison, the number
the phase 2 harness must reproduce, the title convention of 2026-11-02 — and had never been
explained.

**Done**: `notebooks/phase-1/02b_mteb_crash_course.ipynb` (29 cells, the contract of the phase
notebooks, lighter): MTEB as a paper, a leaderboard and a library; BEIR as its retrieval family;
the six steps of `mteb.evaluate` on a retrieval task read in the library's own source, with
GitHub permalinks pinned to the installed 2.20.5 (files checked identical to the tag); nDCG@10
computed by hand on the fixtures, then by `mteb`'s scorer (same 0.473); the real run through
`run_scifact`; the raw `TaskResult`; what the roadmap takes phase by phase and what it leaves.
The notebook runs in CI without `mteb` (every dependent cell skips; verified by forcing the flag
off) and loads no model in sample mode. Listed under notebook 2 in `docs/reading-order.md`.

**Measured** (full run of the notebook, 2026-11-04, Apple Silicon): all-MiniLM-L6-v2 gives the
archived 0.64508 again, to the fifth decimal; `mteb`'s copy of SciFact (`mteb/scifact`) and
ours (`BeIR/scifact`) have identical ids and judgments; **BM25 through `mteb/baseline-bm25s`
scores 0.686 nDCG@10 in 6 s** (the BEIR paper's Anserini: 0.665), four points above MiniLM,
archived in `data/results/bm25_scifact.json`; bge-base-en-v1.5 **without its query
instruction** loses 0.003 (0.7376 against 0.7404), raw `mteb` result archived under
`data/results/mteb_prompt_ablation/`. `PUBLISHED_SCIFACT` gained the `mteb/baseline-bm25s` row
(reference 0.665, the source saying it is Anserini's number), which moved `ClientEncoder.encode`
down one line: notebook 2's anchor updated to L156.

**Not done / deferred**: `bm25s` and `PyStemmer` installed ad hoc in `.venv` (`uv pip
install`), not added to the `bench` group — `uv add` rewrites `pyproject.toml` and `uv.lock`,
both carrying uncommitted work of another session; whether BM25 enters the project through
`bm25s` or through Postgres full-text search is for the phase 2 plan. No leaderboard download,
no API model, no e5 run.

**Incidents**: ruff format turns a config line whose trailing comment passes 100 columns into a
parenthesized three-line assignment, which breaks the "edit one flag" contract of the config
cell — keep config comments short. In zsh, `status` is read-only: `rc=$?`.

## 2026-11-05 — The API arm of the embedding bench had never run: adapter fixed

**Trigger**: notebook 2, part 5, with `RUN_API_BENCH = True` and both keys:
`TypeError: RetrievalEvaluator expects a SearchInterface, Encoder, or CrossEncoder, got
ClientEncoder`. The archived report holds two local models; the API path of `run_scifact` had
been written on 2026-09-03 and never executed to the end.

**Found**, in the order they would have surfaced:
1. `mteb` 2.20.5 checks its encoder protocol with `isinstance` on a `runtime_checkable`
   protocol of four members: `encode`, `similarity`, `similarity_pairwise`, `mteb_model_meta`.
   `ClientEncoder` had two. Notebook 2b said two were enough; that sentence was wrong.
2. `ClientEncoder` called `asyncio.run` per batch. In a notebook it cannot start (the kernel
   runs a loop). From the CLI it opens and closes one loop per batch, and the provider's HTTP
   connections stay bound to the closed one.
3. Measured against a local OpenAI-compatible stub with keep-alive: one `LLMClient` used on two
   loops pays a failed first attempt at every switch (`attempts: 2` in the span), hidden by the
   retry policy. A connection pool belongs to the loop that opened it.

**Done**: `similarity` and `similarity_pairwise` delegate to `mteb`'s own `cos_sim`, so the API
model is ranked by the same code as the open ones. `BackgroundLoop`: one event loop in a daemon
thread for the encoder's lifetime, closed by `run_scifact`. `run_scifact` builds one
`LLMClient` per API model unless one is injected (tests); the CLI no longer builds it, and
notebook 2's cell no longer passes the notebook's client. Three tests, one of which runs in CI
without `mteb` (`BackgroundLoop` from inside a running loop). Notebook 2b, part 3.4 and
glossary: the protocol as it is checked, and why the loop. Source anchors of notebooks 2 and 2b
updated.

**Measured** (offline, fake embedder, then the stub server): `run_scifact` on the API path
runs to the end from a plain script and from inside a running loop; with the bench owning its
client, every call is at one attempt on both sides.

**Not done**: the real run, ~2 min, ~$0.03: notebook 2 with its kernel restarted writes
`data/results/embeddings_scifact_api.json`; `make bench-embeddings` reruns the three models
into `embeddings_scifact.json`. Notebooks 2 and
2b were not re-executed: their working copies hold Christophe's full-mode outputs, and notebook
2 two exploration cells, one with an unused import that `make lint` reports.

## 2026-11-05 — Phase 2 opened: the retrieval harness reproduces three published scores

**Trigger**: `GO PHASE 2`. Plan and consistency audit accepted the same day; the audit's
corrections are in `docs/roadmap/phase-2.md` (what each dataset is for, the two kinds of
arms, the naive extractor for the in-house corpus, "temporal" questions on a static corpus,
what the sample-mode gate guards and what it does not).

**Done, step 1 — retrieval harness** (ADR 011): retrieval metrics as pure functions with
`trec_eval`'s conventions (`eval/metrics/retrieval.py`), bootstrap intervals and paired
comparison (`eval/stats.py`), a `Retriever` contract answering at the document level with two
arms (`retrieval/bm25.py` on `bm25s`, `retrieval/dense.py` on pgvector, chunks folded into
documents by their best chunk, exact or HNSW), open embedding models in process behind the
embedding contract (backend `hf`, `EmbeddingRequest.input_type`), NFCorpus and FiQA wired,
the runner and its record (`eval/runner.py`, `eval/runs.py`), suites declared in
`config/eval_suites.toml` whose arms build the index they read, run history in Postgres
(`eval_runs`, `eval_query_results`), the CLI (`make eval`).

**Done, step 2 — industrialization**: `make eval-gate` (sample mode forced, about three
seconds, baseline `data/results/gate/baseline.json`) as a `pre-push` hook and a CI step;
`make eval-compare` (two archived arms, query by query); `make eval` says how each arm
differs from the archived run it replaces; `make eval-report` builds a self-contained HTML
report (interval plot, tables, paired comparisons) under `build/eval/`.

**Measured** (SciFact test, 300 queries, nDCG@10 with 95% bootstrap interval; full runs
archived under `data/results/runs/retrieval-baseline/`):

| Arm | nDCG@10 | Interval | Recall@100 | Reference | Gap |
|---|---|---|---|---|---|
| BM25 (`bm25s`) | 0.6863 | 0.643 – 0.729 | 0.913 | 0.6863 through `mteb` | 0.000 |
| bge-base-en-v1.5, whole documents, exact | 0.7404 | 0.700 – 0.780 | 0.967 | 0.7404 model card | 0.000 |
| text-embedding-3-small, whole documents, exact | 0.7318 | 0.689 – 0.773 | 0.973 | 0.7313 through `mteb` | +0.001 |
| text-embedding-3-small, chunks 1000/200, exact | 0.7346 | 0.692 – 0.775 | 0.963 | — | — |
| **phase 1 as built**: same index, HNSW defaults | 0.7304 | 0.687 – 0.771 | 0.912 | — | — |
| same index, HNSW `ef_search = 400` | 0.7346 | 0.692 – 0.775 | 0.963 | — | — |

NFCorpus (graded judgments, the check of the linear gain): BM25 0.321 against 0.325 for the
BEIR paper's Anserini, bge-base-en-v1.5 0.3744 against 0.3739 on its model card. Paired
comparisons, same 300 queries: the phase 1 system against BM25
+0.044 [+0.009, +0.079], significant; chunks against whole documents +0.003 [-0.008, +0.014],
not significant; bge-base against text-embedding-3-small +0.009 [-0.015, +0.033], not
significant; HNSW defaults against exact search -0.004 on nDCG@10, not significant, but
**-0.052 [-0.078, -0.028] on recall@100, significant**. Cost: $0.033 to embed SciFact whole
(1.66 M tokens), $0.038 in chunks (10,460 chunks), $0.0001 for the 300 queries of an arm.
The pending re-ingestion of `STATE.md` is done by the suite: the index the API serves
(`scifact-recursive-oai-small`) was rebuilt with titles.

**Incidents / surprises**:
- **The interval is wider than the differences people quote.** On 300 queries nDCG@10 is
  known to ±0.04. The 0.021 between the two BM25 implementations, the 0.009 between bge-base
  and the OpenAI model, are inside it. Only the paired comparison separates dense from BM25.
- **pgvector's HNSW returns at most `hnsw.ef_search` rows (40 by default), whatever the
  `LIMIT`.** Asking for 400 chunks returned 40, without an error: 18 to 35 documents once
  folded. nDCG@10 barely moves; recall@100, what a re-ranker is fed, loses five points. Found
  by measuring exact search next to the index, which is why both arms stay in the suite.
- **A run on fixtures called itself publishable.** The fixtures hold three queries, fewer
  than the sample size of five, so the loader did not flag the dataset as truncated and the
  BM25 arm of a test would have been archived as a number. The run now carries its own
  `sample_mode` flag, set whenever fixtures or simulated embeddings are in play.
- **Thirteen notebook links went stale.** Adding lines to `beir.py`, `types.py`,
  `chunking.py` and `store.py` moved the definitions the notebooks link to;
  `tests/test_notebook_source_links.py` named each one with the anchor to write.
- **Checking an up-to-date index took 40 seconds** for 5,183 documents: two round trips per
  document. The pipeline now reads the state of the source and of the index in two queries.
- `bm25s` fills a ranking with zero-score documents when fewer than `k` share a word with
  the query; the retriever drops them. No effect on the reproduced score.

**Not done / deferred**: the latency columns of these archived runs were measured while the
machine was running tests and another index build; they are re-measured on an idle machine
before being quoted. The FiQA arms (57,638 documents) and the NFCorpus system arm were still
running when this entry was written. Working-tree only: the anchors of notebooks 00, 02 and
2b were rewritten in place; notebooks 00 and 02 carry another session's uncommitted work and
are not part of this commit. No diagram yet for the harness: it comes with notebook 1.

**Next**: step 3 — generation metrics, SQuAD 2.0 and HotpotQA loaders, the judge and its
calibration, which needs Christophe's 50 hand labels.

## 2026-11-05 — A commit deleted the local database: pre-commit, unstaged changes, a running Tilt

**Trigger**: seconds after the commit of the retrieval harness, the background run of the
suite died on `server closed the connection unexpectedly`. `kubectl get ns` no longer listed
`llm-testbench`.

**Found**: `git commit` and `git push` both run pre-commit, and pre-commit stashes every
unstaged change before the hooks and restores it after. The working tree held another
session's uncommitted `Tiltfile`, which moves the namespace object into the `postgres`
resource, and `tilt up` had been running since the day before. Tilt saw its Tiltfile go back
to the committed version and return, twice (commit, then push), and deleted the namespace on
the way: the Postgres pod and its volume, every index, the run history, the API pods. The
commit itself had been built to leave the working tree alone (index written with
`git update-index`); the hooks were the part that did not.

**Lost**: the three SciFact indexes and the NFCorpus index built that afternoon (about $0.10
of embeddings), the `eval_runs` history of the day, and the QASPER index of notebook 2
(`qasper-nb2-oai-small`; notebook 2 rebuilds it at its next run, under one cent). **Not
lost**: every number. The archived runs under `data/results/runs/` were already committed,
which is what decision 6 of ADR 011 is for; it took four hours to be needed.

**Done**: `tilt trigger postgres`, then `api-secrets` and `api`: the namespace, the database
and the API are back (the API stays not ready until its index exists, as designed). The
whole suite was rerun, which rebuilt the indexes and re-measured the latencies on a machine
doing nothing else. Archived runs now hold one line per query, so that a rerun shows in
`git diff` as what moved.

**Rule from now on**: with unstaged changes in the working tree, a commit is built, checked,
committed and pushed from a clean worktree, whose hooks have nothing to stash; the main
working tree only sees its branch move.

**Left open, for whoever owns the Tilt work**: with that Tiltfile change, anyone who checks
out the commit that carries it while `tilt up` runs on the previous version gets the same
teardown. A namespace that holds the only copy of the local data should not be an object a
Tiltfile edit can delete.

**Re-measured after the rebuild** (same day, machine idle, one query at a time from the
laptop). Reproductions unchanged to the fourth decimal on exact search (BM25 0.6863, bge-base
0.7404; text-embedding-3-small 0.7323 where the first build gave 0.7318: the API does not
return bit-identical vectors twice). **The same HNSW index built twice does not score the
same**: the phase 1 system as built went from 0.7304 to 0.7269 nDCG@10 (recall@100 0.912 to
0.908), while exact search on the same vectors stayed at 0.7346. As built, against BM25:
+0.041 [+0.004, +0.076], still significant; against exact search: -0.055 [-0.082, -0.030] on
recall@100. NFCorpus: bge-base against BM25 +0.053 [+0.034, +0.073]. Latency, p50: BM25
0.2 ms; the dense arms on the OpenAI model 230 to 340 ms, of which about 220 ms is the API
call that embeds the question; the search itself 34 ms with HNSW defaults, 95 ms with
`ef_search = 400`, 138 ms exact, on 10,460 chunks; bge-base in process 20 ms to embed and
42 ms of exact search. Verifying an index that is up to date: 0 to 2 seconds.

## 2026-11-05 — Phase 2, step 3, first half: generation measured without a judge, a judge ready to calibrate

**Trigger**: the budget. "$35 is too expensive for me": the lean option was chosen, about $5
under a hard cap of $10, with arXiv papers (CC BY 4.0) confirmed as the in-house corpus
(`docs/decisions.md`, ADR 012).

**Done**: a QA dataset type and the SQuAD 2.0 loader (seeded subsample, half unanswerable);
the generation runner on gold passages, through the API's own prompt and parser
(`eval/generation.py`); the metrics that need no judge (`eval/metrics/generation.py`); the
judge (`eval/judge.py`, two rubrics as versioned prompts, yes or no, reasons first);
Cohen's kappa (`eval/agreement.py`); the calibration set and its terminal annotation tool
(`eval/calibration.py`, `eval/annotate.py`, `make eval-calibration-set`, `eval-annotate`,
`eval-calibrate`); a spend ledger with a cap (`eval/spend.py`, `data/results/spend.jsonl`);
generation arms in the suites and in the gate. Structured outputs now report the cost of
every attempt, repairs included.

**Measured** (SQuAD 2.0 validation, 100 questions drawn with seed 0, half unanswerable,
`anthropic/claude-sonnet-5-5` on the gold paragraph, archived in
`data/results/runs/generation-baseline/`):

| Metric | Rate | 95% interval | On |
|---|---|---|---|
| Correct refusal | 0.74 | 0.62 – 0.86 | 50 unanswerable questions |
| Over-refusal | 0.04 | 0.00 – 0.10 | 50 answerable questions |
| Contains the reference answer | 0.92 | 0.84 – 0.98 | 50 answerable questions |
| Answer F1 (SQuAD) | 0.22 | 0.18 – 0.26 | 50 answerable questions |
| Cites an excerpt | 1.00 | — | 61 answers given |
| Invents a citation | 0.00 | — | 61 answers given |

Asked three times, 50 questions: the refusal flips on 8% of them, the wording changes on
52%. Latency p50 1.6 s, p95 3.6 s. Cost $0.42 for 200 calls; $0.61 spent in all.

**Incidents / surprises**:
- **One unanswerable question in four gets an answer, and every one of those answers
  carries a citation.** "Cites an excerpt" is at 100% and "invents a citation" at 0%: by
  the two citation metrics the system is perfect, on the very answers that should not
  exist. A citation says where the model looked, not that the excerpt says it. That gap is
  what the groundedness judge is for.
- **SQuAD's F1 says 0.22 where the reference answer is in the text 92% of the time.** The
  generator answers in a sentence, the reference is two words. A harness that copied the
  dataset's own metric would report a broken generator.
- **The cost estimate was off by two.** I assumed 40 output tokens per answer; the model
  wrote 122 on average, and an output token costs five times an input token. "Answer
  concisely" in the prompt does not buy short answers. The ledger caught it at $0.42, not
  after the fact.
- **The same question, asked three times, is refused once and answered twice on 8% of the
  questions.** With 50 questions per rate, that noise is of the order of what one prompt
  change would be credited with.

**Not done**: the judged baseline, which waits for the calibration, which waits for
Christophe's 50 labels; QASPER and HotpotQA generation arms; end-to-end runs; the bias
experiments (self-preference needs a second generator, not paid for until the judge is
shown usable); the notebooks and the diagram.

**Next**: Christophe runs `make eval-annotate` (50 items, two keys each, resumable), then
`make eval-calibrate`.

## 2026-11-05 — Phase 2, step 3, second half: end to end, and what the first clock found

**Trigger**: the rest of step 3 does not wait for the 50 labels: the HotpotQA and QASPER
arms, the end-to-end runs, the closed-book probe, the bias probes of the judge.

**Done** (ADR 013): one generation runner for three contexts, gold passages, chunks
retrieved by the API's own document source, or nothing (`eval/context.py`); each
end-to-end answer records whether the gold passages were among the chunks it was handed,
and the answerable questions are split four ways, passages found or not, reference answer
given or not (`attribution`). HotpotQA loader: the paragraphs of 1,000 questions of the
distractor setting pooled into one corpus of 9,789, as a retrieval dataset and as a
question-answering one. QASPER answers and evidence: 887 of the 1,005 validation questions
can be scored from the text, the search scoped to the paper. Closed-book probe as a third
context with its own prompt (`prompts/closed_book.md`). Bias probes of the judge
(`eval/bias.py`, `make eval-bias`): padding, citation markers removed, excerpts reversed,
against a repeat control; to run once the judge is calibrated. The gate covers 12 arms.
Notebook 1 of phase 2 (`notebooks/phase-2/01_measuring_a_rag.ipynb`, 30 cells).

**Measured** (full runs archived under `data/results/runs/`, 95% bootstrap intervals):

| | Reference answer given | Correct refusal | Over-refusal | All gold passages found |
|---|---|---|---|---|
| HotpotQA, gold context (100) | 0.85 [0.78, 0.92] | — | 0.04 | — |
| HotpotQA, **end to end** (100) | **0.57** [0.47, 0.67] | — | 0.31 | 0.60 |
| HotpotQA, closed book (100) | 0.53 [0.43, 0.63] | — | 0.20 says it does not know | — |
| QASPER, gold context (50 answerable) | 0.28 | — | 0.12 | — |
| QASPER, **end to end** (50 + 50) | 0.20 | **0.74** [0.62, 0.86] | 0.16 | 0.54 |
| QASPER, closed book | 0.00 | — | 0.98 says it does not know | — |
| SQuAD 2.0, closed book (50 answerable) | 0.38 [0.26, 0.52] | — | 0.34 says it does not know | — |

Retrieval alone on the HotpotQA pool (1,000 questions): BM25 recall@5 0.737, nDCG@10 0.756;
the system as built 0.806 and 0.816. FiQA (648 queries): bge-base-en-v1.5 on whole
documents 0.406 (model card: 0.407); the system as built 0.417 [0.389, 0.445], recall@100
0.642; the same index searched exactly 0.428 and 0.764.

**Incidents / surprises**:
- **The end-to-end score hides who failed.** HotpotQA: 43 wrong in 100. In 33 of them a gold
  paragraph was missing from the five chunks, and in 29 of those the generator refused, as
  it should. Ten failures are the generator's. A reader of "57%" alone rewrites the prompt.
- **The HNSW default costs 12 points of recall@100 on FiQA** (0.642 against 0.764 exact,
  [-0.141, -0.103]), twice what it costs on SciFact. Forty candidates is the same forty
  whatever the corpus.
- **A search took 22 seconds on a fresh index, and no retrieval metric would have shown
  it.** The chunks of the HotpotQA pool went into tables shared with other sources;
  Postgres had sampled its statistics before the load, expected one row for the new source
  and joined 10,635 chunks against 4,896 documents each. Autovacuum would not have fixed it
  (the load was under a tenth of the tables). The pipeline now ends a load with `ANALYZE`
  (`PgVectorStore.analyze`); the same search takes 5 ms. Found because an end-to-end run
  has a clock.
- **Half of the first closed-book answers were empty, and the run called them answers.**
  The generator reasons before it writes; those tokens are output tokens, counted against
  the cap and absent from the text. The probe was capped at 120 tokens: 56 empty answers in
  100, a finish reason of `length`, no error, and a table saying the model "answers 99% of
  the questions". At the harness's 512, 9 QASPER answers in 100 were cut. The API had a
  third cap, 1,024. One constant now (`MAX_OUTPUT_TOKENS = 4096`, shared), every answer
  records whether it was cut, every run reports the share. It also explains both cost
  estimates that were off by two: an answer of 60 visible tokens is billed 120 to 400.
- **Without any document, the generator gives the reference answer on 53% of the HotpotQA
  questions**; the whole system scores 57%. Of its 57 right answers, 38 are on questions
  the model answers alone. On the 47 it does not know, the system gets 19 right (40%) and
  the gold context 36 (77%): that is the system's own contribution, and it is not 57%.
  On 15 questions the model knew and the system refused or erred: told to rely only on the
  excerpts, it did.
- **`contains the reference answer` does not work on QASPER**: 0.28 on the gold evidence.
  The references are spans and free-form sentences; a right answer in other words does not
  contain them. Half of what the table calls "found but wrong" cannot be graded by code.
- **The scoped QASPER search was checked against an exact search before being trusted**:
  identical on the 887 questions (Postgres filters the documents first and compares their
  chunks one by one; the index is not used). An `iterative` and an `exact` mode were
  written for the chunk search, measured identical, and removed.
- A background run was started twice by mistake (`&` in a shell line): two processes
  harvested arXiv at once for seven minutes, until the stale one was killed. Nothing was
  written by it.

**Cost**: $4.11 spent on the baseline so far, of the $10 cap (`data/results/spend.jsonl`;
the drafting of the golden set, next entry, is not counted here), against "about $5"
announced for the whole baseline. $1.15 of it bought nothing: a run made before the
`ANALYZE` fix and interrupted ($0.09), closed-book runs made at a cap of 120 tokens and
void ($0.26), QASPER runs made at 512 and run again ($0.80). The rest of the overrun is
reasoning tokens, which no estimate of mine had counted.

**Not done**: the calibration and the judged baseline (they wait for the 50 labels); the
self-preference probe (a second generator and a second judge, about a dollar, not before
the calibration); a judge rubric for correctness against the reference answer, which
QASPER needs; SQuAD 2.0 and HotpotQA on the gold context were not run again at the new cap
(2 calls in 200 and 0 in 100 had reached the old one; the SQuAD answers are in the
calibration set being labelled).

**Next**: step 4, the in-house corpus and the golden set.

## 2026-11-05 — The gate went red in CI on its first new arms: ties in the fixtures

**Trigger**: the CI of the previous commit failed on the evaluation gate, and the next
push was refused by the same gate, with other numbers: `hotpotqa-bm25` nDCG@10 0.973
instead of 1.000 in CI, `hotpotqa-retrieved` complete context 0.667 instead of 1.000
locally. The gate had passed a minute earlier on the same code.

**Found**: one fixture question had two paragraphs with exactly the same score, for BM25
(0.7672 and 0.7672) and for the simulated embedder (0.2828 and 0.2828), one of them gold,
at the rank where the metric is decided. Equal scores have no order: `bm25s` returns them
in an order that depends on the platform, and Postgres in the order it finds the rows,
which changed after an `ANALYZE`. The baseline had been recorded on one of the orders.

**Done**: BM25 ties are broken by document id, largest first, as `trec_eval` does
(`retrieval/bm25.py`); the four BM25 arms were run again on the real datasets and do not
move (SciFact 0.6863, FiQA 0.2514, HotpotQA pool 0.7558; NFCorpus 0.3210 against 0.3214,
[-0.0013, +0.0000]). The HotpotQA and NFCorpus fixtures were reworded so that no two
documents tie, and three tests fail first if a fixture gets a tie where a metric is
decided. The gate gives the same 75 values on five runs, under different hash seeds.

**What it says about the gate**: a regression gate on tiny fixtures is only as stable as
its fixtures are unambiguous. Mine was green by luck for a day. The dense arms keep one
weakness I did not remove: the chunk search orders equal distances as the database finds
them; the fixtures now have none, and a test says so for HotpotQA, but nothing in the SQL
enforces an order.

## 2026-11-05 — Phase 2, step 4: a corpus no model has read, and 83 drafts waiting for a reviewer

**Trigger**: phase 2.5 and 2.6. The corpus was decided in the morning (arXiv papers under
CC BY 4.0); everything else about it was still to choose.

**Done** (ADR 014): the arXiv client (`eval/corpus/arxiv.py`: the OAI-PMH interface for
licenses and the date of each version, one request every three seconds); the reference
text from arXiv's HTML rendering (`eval/corpus/reference.py`); the selection and the
manifest (`eval/corpus/build.py`, `manifest.py`, `config/corpus.toml`, `make corpus-build`,
`corpus-download`, `corpus-verify`); the naive PDF extractor (`ingest/pdf.py`, `pypdf`);
the golden set: taxonomy and states of a question (`eval/golden/types.py`), drafting with
quotes checked word for word (`drafting.py`, `prompts/golden_draft.md`), two automatic
checks of the drafts (`make golden-probe`), the terminal review (`review.py`,
`make golden-review`), the frozen set and its changelog (`store.py`, `make golden-freeze`),
the golden set as a dataset of the harness on the naive or the reference text
(`dataset.py`). 34 tests, offline.

**Measured**:
- **Corpus**: 2,762 fresh candidates under CC BY 4.0 in sixteen days of computer science;
  355 examined, 200 kept, all first submitted on 2026-10-20 or 2026-10-21. Median document:
  63,740 characters, 9 tables, 11 displayed formulas; 66 have a footnote. 55 cs.LG,
  52 cs.CV, 40 cs.CL, 39 cs.AI, 14 others.
- **Drafts**: 83 on 30 documents, 15 of each kind except temporal (8). 106 quotes, all
  found word for word in their paper. Asked without any document, the generator said it
  did not know on 78 drafts and gave the reference answer on 2; on HotpotQA it gives it on
  53 questions in 100. 3 of the 15 drafts marked unanswerable are answered deeper in their
  paper, according to a second model that quoted the passage.
- **Cost**: $0.57 for the drafts (about $0.02 a document), $0.07 for the closed-book check,
  $0.05 for the second reading. $4.81 spent in all.

**Incidents / surprises**:
- **The first selection kept 2 papers in 70.** I had required two footnotes, from an idea
  of what a paper looks like. Counted on the first 24 candidates: tables are everywhere
  (median 7), footnotes almost nowhere. The thresholds were set again on that count, and
  every page fetched is now kept in the cache so that choosing thresholds costs arXiv
  nothing twice.
- **"Published after the cutoff" could not be established from a cutoff.** I do not know
  the training cutoff of the models, and a provider's statement of it is not evidence. A
  release date is: the floor is after the day each model is known to have been available,
  from dated files of this repository. All 200 documents were first submitted after it.
- **arXiv lists records by last modification**: two days of "recent" records held papers
  first submitted in 2013. The date that counts is the one of the first version.
- **The provider refuses a schema with an optional field.** Strict structured outputs want
  every property required and no open object; the drafting schema had defaults and failed
  with a 400 on the first call. The judge's schema was already strict, by luck.
- **An "unanswerable" draft is a claim about the whole paper made by a model that read a
  third of it.** The drafter is given the first 24,000 characters. A second, cheaper model
  now rereads the whole paper for those drafts and must quote; 3 in 15 were caught. The
  reviewer is shown the passage, and how much of the paper the drafter read.
- The temporal kind is thin: 8 drafts in 15 requested, several of them on citation years.
  Research papers state few dates. To be seen at the review; the kind may not survive.

**Not done**: the review (Christophe, two to three hours: `make golden-review`), so no
frozen set and no measurement on it; the arms that run the golden set on the naive text
and on the reference text; the ingestion of the corpus (it waits for those arms); the
completion probe of contamination (continue a passage, measure the overlap), dropped for
the closed-book probe, which gave a clear answer for a quarter of the price.

**Next**: notebooks 2 to 4; then the calibration and the review, which are Christophe's.

## 2026-11-05 — Phase 2: the three other notebooks

**Done**: notebooks 2 (LLM-as-judge, 20 cells), 3 (contamination, 16 cells) and 4 (building
a golden set, 23 cells) in `notebooks/phase-2/`, same contract as notebook 1: nothing
implemented in them, links to `src/` with line anchors, live cells on fixtures with
scripted models, numbers read from the archived runs, guided experiments in the
configuration cell. An offline stand-in for arXiv (`offline_fetch`) and a two-page PDF
fixture, so that notebook 4 runs the corpus selection, both texts of a document, the
drafting, the two checks, the review and the freeze on one fixture paper. Three class
diagrams (retrieval evaluation, answers and judge, corpus and golden set), checked against
the code by `tests/test_diagrams.py`. `docs/reading-order.md` lists the phase.

**What the notebooks say that the tables did not**:
- Notebook 3: on the 47 HotpotQA questions the model does not answer alone, the system is
  right 40% of the time and the gold context 77%. The headline numbers (57 against 85)
  understate the room for improvement by half, and overstate the baseline.
- Notebook 2: a judge that says "yes" without reading agrees with the labels 60% and 80%
  of the time on five toy items, at a kappa of zero. With 48 "yes" in 50, one disagreement
  takes kappa from 1.00 to 0.66; with 25, to 0.96.
- Notebook 4: a row of a table quoted from the reference text ("Dense | 0.74") does not
  exist in the PDF's text. The golden set will measure that on purpose.

**Incidents / surprises**:
- Three sentences I had written from memory did not survive the outputs: the two guessable
  drafts are both arithmetic (I had described one as a release order), the drafter read 37%
  of a median paper (I had written 38), and a kappa experiment I proposed gives +0.38 where
  I announced a negative value. Each was caught by reading the executed cell next to the
  prose, which is the only review a notebook gets before its reader.
- Rendering the diagrams (`npx mermaid-cli`) was not permitted in this session: they are
  checked against the code, not seen.
- The diagrams sit in `docs/diagrams/`, which is another session's uncommitted work; they
  are left uncommitted with it.

**Not done**: the numbers of notebook 2 (they wait for the 50 labels) and of notebook 4's
frozen set (they wait for the review); the judged baseline; the golden set's arms; the
README; the phase closing.

**Next**: Christophe's two tasks, in either order: `make eval-annotate`, `make golden-review`.

## 2026-11-10 — Phase 2, notebook 1: arm, run and suite defined before they are used

**Done**: Christophe opened notebook 1 and asked what an arm and a suite are, and what the
notebook expects him to know. Both words were used from the configuration cell on; "arm"
was defined in part 4.1, "suite" nowhere. The opening cell now says what phase 1 built in
four definitions (chunk, embedding model, index, generator), what to take away, and how
the cells run. A section closes part 1, before the configuration cell: dataset, metric,
arm, run and suite on one example (keywords against meaning on SciFact), the suites of the
phase with the question each answers, and how to read the name of an arm. A live cell
after the imports prints the suites of `config/eval_suites.toml`, one arm as the file
declares it and the run archived for it (`SHOW_SUITE`, `SHOW_ARM`). The glossary gains
harness, baseline, fixtures, dataset, metric and suite. 33 cells.

**Incidents / surprises**:
- Part 4.3 held five `{L("module", "name")}` placeholders that the generation script of
  2026-11-05 never rendered into links, visible as such in the committed notebook. The
  link test could not see them: it checks the links that exist, not the ones that are
  missing. Replaced by real links, which the test now covers.

**Not done**: notebooks 2 to 4 use "arm" and "suite" without redefining them; they lean
on notebook 1, as `docs/reading-order.md` says.

## 2026-11-10 — Every name of the arm layer says which kind of arm it is about

**Done**: reading `eval/suite.py` after notebook 1, Christophe asked whether an arm is a
retrieval arm unless said otherwise. It was. Retrieval arms were built first and took the
bare names; generation arms came later with a prefix; the base class of both was named
after the index that half of its subclasses never read. Renamed at his request:

- `ArmConfig` → `RetrievalArmConfig`, and `IndexedArm` → `ArmConfig` (what both kinds share);
- `run_arm` → `run_retrieval_arm`, `load_dataset` → `load_retrieval_dataset`;
- `SuiteConfig.arms` → `SuiteConfig.retrieval`, and the key of `config/eval_suites.toml`,
  `[[suites.<suite>.arms]]` → `[[suites.<suite>.retrieval]]`.

The docstring of the module carries the table of the two kinds, notebook 1 shows the same
table with links, diagram 11 follows. No behaviour changed: the gate passes on the same
baseline (75 checks) and no archived run is touched (a run records the name of its arm,
not a class).

**Careful**: `ArmConfig` now names the base class; before this date it named the retrieval
arm. Earlier entries of this journal use the old meaning.

**Not done**: the same habit remains in two places outside `suite.py`. In `eval/cli.py`,
`run_suite` runs the retrieval arms only, next to `run_generation_suite`. In `eval/runs.py`,
`load_run`, `save_run` and `format_runs` are about retrieval runs only, next to
`load_generation`, `save_generation` and `format_generation`. Renaming them changes the
code cells of notebooks 1 to 3, which then have to be executed again.
