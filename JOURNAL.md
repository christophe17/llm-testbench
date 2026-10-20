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
