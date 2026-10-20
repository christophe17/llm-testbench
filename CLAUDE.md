# MISSION BRIEF — llm-testbench

This file is the working contract, loaded at every session. It contains only what is needed
on every turn: who I am, how we work, the protocol, the stack, the rules.
The rest lives elsewhere and is read **when it is needed**:

| File | Content | When to read it |
|---|---|---|
| `docs/roadmap/README.md` | overview of the phases, schedule, table of datasets | at the start of each phase |
| `docs/roadmap/phase-N.md` | the statement of phase N, amendments integrated | at the start of phase N, and at every resumption mid-phase |
| `docs/decisions.md` | dated register of the decisions made along the way, with references to the ADRs | at every session resumption |
| `STATE.md` · `JOURNAL.md` · `docs/adr/` | current state, dated history, structural decisions | at every session resumption |

When a decision changes the brief, **we fix the text concerned** (here or in the phase
file) **and** we add a dated line to `docs/decisions.md`. Never an amendment that
contradicts a text left in place.

---

## 1. Who I am and what I want

Developer working since 2006: web, then DevOps, then classical Machine Learning
(XGBoost, SVM, PCA, regressions), then Deep Learning (transformers, CNN, diffusion), then MLOps.
All learned on the job, as a freelancer. The detailed profile (years, background, constraints) is
held by the program (`~/Roadmaps/program/docs/00-context.md` §1); this brief does not restate it.

**Target.** The career strategy is held outside this repository, in
`~/Roadmaps/program/docs/01-career-strategy.md` (decision PD-8); Switzerland (banking, pharma,
insurance) is a constraint there. This testbench serves a positioning: *AI Engineer who can ship
to production and who measures*. A permanent AI Engineer position at a startup / scale-up in
France is a fallback of the program, not its target. My edge is not deep learning, it is my
ability to operate, observe and quantify a system. Since 2026-10-19 (PD-18), the program no
longer has a production project of its own: `~/Project/sherpapier` is frozen and AgentCore is
no longer required. This testbench, once its phases 0 to 8 are studied, is the proof for
freelance engagements (ML, LLM or agentic); the production proof is the engagement itself.
This repository remains the lab and the teaching reference.
No certification (PD-9).

**What I already master very well**: Kubernetes, Terraform, CI/CD, Docker, classical
observability, service architecture, SQL, Python. Generate the infra directly at production
level — but **explain it** (see §2.D): I can read it, I still want to loop back
on every AWS choice.

**What I came to learn, and it is the primary goal of the project**: LLM engineering in
production. Vector stores, chunking, hybrid retrieval, re-ranking, evaluation, multi-source
agents, text-to-SQL, MCP, LLM observability, quantization and self-hosted inference,
security.

### Nature of the deliverable: a testbench, not a product demo

**Structural decision, do not question it.** The public repo is a **measured technical
testbench**: every implemented technique is measured on **public datasets with
already-annotated ground truth**, and compared to the published scores in the
literature.

The main reason is a teaching one: the reference scores give me an objective
benchmark. If my BM25 comes out far below the literature, my implementation is wrong and
I know it the same day. On an in-house corpus, I have no benchmark and I can spend three
weeks optimizing a broken system without noticing.

Direct consequence: **I do not have to become an expert in any business domain.** Massive
manual annotation is replaced by public datasets, plus a small in-house golden set
of 50 to 80 questions whose only purpose is to show that I master the method of
building an evaluation from scratch.

The system stays **deployable and operated** for real — API, cluster, observability, costs. It
is not a giant notebook. But its selling point is measurement, not the use case.

**A consequence to own: there are no users and no real traffic.** Everything that assumes
production — online A/B testing, canary, drift, feedback — will be demonstrated on a **synthetic
traffic generator** replaying the queries of the public datasets according to configurable
load profiles. This is a real limitation of the setup: it must be written in black and white
in the README, never disguised.

**Public repo, no client content.** Any client deployments live in separate repos;
nothing from a client comes in here.

---

## 2. How we work — THE MOST IMPORTANT POINT

**I learn by reading explained code, not by writing code.** You write 100% of the code. My
job is to read, understand, question, decide, and run experiments by changing
parameters.

For each phase, two coupled deliverables.

### A. The production code, in `src/`

Real code, tested, typed, deployable.

### B. A teaching notebook, in `notebooks/phase-N/`

**Strict contract — follow it to the letter:**

1. **The notebook implements NOTHING.** It `import`s from `src/` and runs the project's real
   code. If you rewrite a simplified version in the notebook, you have failed: I must
   learn the code that runs, not a parallel toy.
2. To show the code, use `inspect.getsource()` on the real functions and classes, or
   display file excerpts with their path, then explain block by block.
3. Mandatory structure:
   - **The problem**: what we are trying to solve, why the naive solution is not enough.
   - **The options**: 2 or 3 possible approaches, why this one.
   - **Guided reading of the real code** from `src/`, commented where it is subtle.
   - **Run** with **visible intermediate outputs**: the returned chunk, the final prompt
     sent, the generated SQL query, the trace, the raw response. I want to see what
     happens, not only the result.
   - **Pitfalls**: what breaks for real, what the tutorials do not say.
   - **Guided experiments**: 2 or 3 configuration cells at the top that I can
     edit to rerun and observe the effect, without writing code.
   - **The numbers**: measured impact on quality, latency, cost — and **comparison
     with the published scores** when the dataset has them.
   - **Interview questions**: 4 to 6 questions with the expected answers in a collapsed
     cell.
   - **What we did not do, and why**.
4. **The notebook must run end to end.** `nbmake` in CI: a broken notebook
   breaks the build. A full benchmark on every commit costs too much: sample mode
   driven by `LLM_TESTBENCH_SAMPLE=1` — CI, offline and without secrets, checks that everything
   runs on a tiny extract; the published numbers come from full runs
   launched by hand and archived (ADR 003).
5. All prose, identifiers and code in **English**; no French anywhere in the repository
   (decision of 2026-10-20). ~40 cells max, otherwise split.
6. **Beginner level on LLM/IR concepts.** Problem first, every term defined at its
   first appearance, toy example before any abstraction, step-by-step progression, final
   glossary. Never assume the retrieval/evaluation vocabulary is known (DevOps/K8s/SQL, yes).

### C. Conversation rules

- **Explain before coding.** For any non-trivial decision: 2 options and your call,
  in ten lines, before writing.
- **Contradict me.** If I ask for a bad idea, say so.
- No flattery, no polite recaps.
- If a choice commits me (dataset, provider, cost), **ask the question and wait**.

### D. The infra is explained too

Markdown guides in `docs/infra/`, same structure as the notebooks (problem, options,
guided reading of the real code, run with expected outputs, pitfalls, interview questions,
not done), run by me from the CLI. K8s/Terraform vocabulary is known; every AWS choice and
every pitfall made explicit. No infra notebook (credentials and cluster required, incompatible
with the offline CI).

---

## 3. Phase protocol

You work on **only one phase at a time**, and only when I write `GO PHASE N`.

1. **Plan** — reread `docs/roadmap/phase-N.md`, do the consistency audit (§6), then: what you
   will build, the open decisions. One page max, then you wait for my go-ahead.
2. **Code** — tests first when possible, then implementation, then infra.
3. **Notebook** — following the contract above.
4. **Measurement** — you run the evaluation and produce the numbers. From phase 3 on,
   **a phase without numbers is not finished**.
5. **Traces** — `JOURNAL.md`, ADRs in `docs/adr/`, `STATE.md`, `docs/decisions.md`.
6. **Debrief** — in 10 lines: what is done, what I must read first, where I will
   get caught out in an interview, what remains weak in our implementation.

**Everything happens on `main`** (ADR 008): no phase branch, no PR. Small,
well-described commits, pushed when the local CI passes; GitHub CI runs on every push. The
narrative of a phase, which used to go in the PR description, goes in its closing entry in
`JOURNAL.md`.

### Session resumption

At each new session, before answering: `STATE.md`, the latest entries of
`JOURNAL.md`, `docs/decisions.md`, the 3 latest ADRs, and `docs/roadmap/phase-N.md` for the
current phase.

---

## 4. Stack and infra — frozen decisions

- Python 3.12, `uv`, ruff, mypy strict, pytest, pre-commit. Package: `llm_testbench`.
- FastAPI + Pydantic v2, async, SSE streaming.
- PostgreSQL + pgvector as the vector database (psycopg 3 with raw SQL, HNSW index).
- Multi-provider LLM abstraction from the first call, two implementations: native Anthropic
  (also serves Bedrock) and OpenAI-compatible (OpenAI, OpenRouter, Mistral, then vLLM/Ollama).
  Model = string `backend/model`. **OpenRouter is a breadth backend, never the sole
  path** (ADR 006).
- **Data governance, a property of the LLM layer**: data class on every
  request, backend registry with governance metadata, deny-by-default
  policy, traced decision; also applies to embeddings and the judge (ADR 006).
- **Prompts in versioned files**, never hard-coded.
- Self-hosted Langfuse, OpenTelemetry with the GenAI semantic conventions.

### Infra: production level

- **Local dev**: `k3d` + Tilt. Not Docker Desktop's Kubernetes. **macOS Apple
  Silicon** machine — flag any image without an `arm64` build rather than making me suffer
  emulation.
- **Cloud: AWS**, `eu-west-3`. EKS, ECR, RDS Postgres with pgvector, S3, Bedrock as one
  provider among others. Terraform, encrypted remote state, **a single `dev` environment,
  ephemeral**: no `prod` environment as long as there are no users; the canary and the
  shadow of phase 5 are demonstrated inside this cluster, not between two (ADR 009).
- **Cost**: the cluster does not run 24/7. `make infra-up` / `make infra-down`, no idle cost
  item (watch out for NAT Gateway), estimated monthly cost documented per module. No budget
  cap a priori, but every item is estimated before commitment.
- Helm, External Secrets + AWS Secrets Manager, HPA, probes, PDB, sized resources.
- **Deployment**: `make deploy` from the workstation, and the same deployment through GitHub
  Actions with an OIDC role (arm64 build, ECR, Helm), triggered by hand; the test CI stays
  offline and without secrets (ADR 003, ADR 009, guide 09).
- **AWS services, entry rule** (ADR 009): an AWS service comes in when it is the natural
  answer to a block already planned by the roadmap (SQS for the phase 5 queue, ADOT for the
  collector, Karpenter, Cost Anomaly Detection), or as a **measured comparison arm**
  (Bedrock Knowledge Bases in phase 3, Guardrails in phase 7, AgentCore in phase 4 if the
  question comes back). Never as the sole path, never to learn a service that nothing
  justifies. Every AWS service has an equivalent local implementation behind the same
  abstraction (Postgres `SKIP LOCKED` for SQS, vanilla OTel collector for ADOT).
- Observability via Helm: Prometheus, Grafana, OTel collector, Langfuse. Dashboards versioned
  as JSON. Locally, only the bare minimum.
- **GPU in phase 6 only.** Default path: specialized provider, dedicated Terraform module,
  ephemeral, obvious teardown. Second target if the G quota is granted: a GPU node group
  on the existing EKS, measured against the first (ADR 009).
- **Portability**: the application code stays cloud-agnostic, the AWS-specific part lives in
  `infra/`.
- The infra must not become the topic. You generate it fast and well, I review it, we move on.

### Repo structure

```
.
├── CLAUDE.md · STATE.md · JOURNAL.md · Makefile
├── src/llm_testbench/
│   ├── app/          # API, service
│   ├── llm/          # provider abstraction, retries, cache, structured output, governance
│   ├── sources/      # generic Source interface + connectors (docs, SQL, API, images)
│   ├── ingest/       # parsing, chunking, embeddings, indexing
│   ├── retrieval/    # search, hybrid, reranking
│   ├── generation/   # chains, context assembly
│   ├── agents/       # orchestration, tools, guardrails
│   ├── eval/         # harness, metrics, judges, benchmark runners
│   ├── classic/      # phase 5B only: classical models as comparison arms
│   └── obs/          # instrumentation, cost, traces
├── prompts/          # versioned prompts
├── data/             # public datasets (cache) + versioned in-house golden set
├── notebooks/        # one subfolder per phase: phase-N/NN_slug.ipynb, NN = order within the phase
├── infra/            # terraform, helm, k8s
├── docs/             # roadmap/, adr/, infra/, decisions.md
└── tests/
```

---

## 5. The roadmap

In `docs/roadmap/`: an overview `README.md` and one file per phase (0 to 10, plus
5B). **A single system, which grows with each phase. Never a second project.** The "weeks"
are units of relative effort, not deadlines.

---

## 6. Quality rules and anti-patterns

**Always:** tests before implementation when possible, with network calls mocked so that
the suite runs offline · one ADR per structural decision (context, options, decision,
consequences) · before/after numbers from phase 3 on · prompts in versioned files ·
a technique without gain is removed and documented · one run manifest per training run
(phases 5B and 6).

**Consistency audit, at the start of each phase.** This project pivoted during design:
from a product built on a business corpus to a testbench on public datasets. Some parts
of the roadmap may still carry justifications inherited from the old logic — living
corpus, data freshness, domain expertise, product demo, real users.
**Before starting a phase, reread its statement and ask yourself whether each block still has
a reason to exist in the current logic.** If a block is floating, flag it and propose either to
remove it or to rephrase it on a valid justification — do not code it mechanically
because it is written. Also flag to me any contradiction between two sections of the brief.

**Never:** no simplified version of the code in the notebooks · no certification · no
reimplementing a transformer from scratch · no fine-tuning before phase 6 · no
second project · no stacking frameworks for show. Third-party frameworks
(LlamaIndex, smolagents, OpenAI Agents SDK, CrewAI) come in only as **measured comparison
ports** in the benchmark material; `src/` keeps a single implementation.

**And specifically for this project:** the subject is retrieval, agents, measurement and
operations. Never propose to widen the scope toward prediction, scoring
or business modeling **as a deliverable**: no predictive model is built for
its business value, no prediction task is added for its own sake. **Sole exception,
named and bounded — phase 5B**: classical models are trained there only as
comparison arms for an architecture trade-off, on a public dataset with a published reference,
measured by the common harness. Three locks: (1) no other prediction task, in
any other phase, without an explicit amendment of the brief; (2) default hyperparameters or
a bounded, documented search — an honest comparison arm, not an optimized model;
(3) the classical code lives in `src/`, tested and typed, but is never exposed by the API nor
called by the agent. Any proposal that reuses this module outside 5B is to be treated as a
violation of this rule, not as a natural extension.
