# STATE

> Snapshot of the project state. Updated at each work session.
> Detailed history in `JOURNAL.md`, decisions in `docs/adr/`.

## Current phase

**Phase 1 — Production skeleton: built** (2026-09-03), merged into `main` on
2026-10-16 with PR #2 (PR #3). Since then, everything happens on `main`, with no branch or PR
(ADR 008). What remains requires Christophe's actions (keys, AWS account), not code.
**Resumption audit of 2026-10-19** (ADR 009, `JOURNAL.md`, `docs/decisions.md`): brief and
infra corrected — a single environment, deployment via GitHub Actions and OIDC, database URL
composed in the cluster, AWS services entry rule, Claude 5.5 by default. No change of
course; the testbench proves nothing until phase 1 is studied and run.

## Done in phase 1 (2026-09-03)

- **LLM layer** (`src/llm_testbench/llm/`, ADR 006): neutral types; data governance
  (classes, dated backend metadata, deny-by-default TOML policy, traced decision); registry
  `config/llm_backends.toml` (anthropic, openai, openrouter, bedrock, local); dated price
  table; versioned strict Jinja2 prompts with fingerprint; retry/backoff/jitter, circuit
  breaker, timeout, budget, exact and semantic cache; Anthropic (including Bedrock) and
  OpenAI-compatible providers on the official SDKs; embeddings; structured outputs with
  bounded repair; `LLMClient` facade; OTel traces (`gen_ai.*` + `llm_testbench.*`); network
  simulators (scripted transport, toy and hashed embedders).
- **Sources and ingestion** (ADR 007): homogeneous `Source`/`Evidence`/`Provenance`/`Citation`;
  parsing (text, markdown, sections); recursive chunker (phase 3 baseline); Postgres schema
  (documents, chunks, index registry, one HNSW vector table per index); asynchronous psycopg
  store; idempotent pipeline; QASPER loader; `DocumentSource`; cited answer with refusal
  sentinel.
- **API**: `/chat` JSON, `/chat/stream` SSE, `/healthz`, `/readyz` (503 with a reason),
  `/sources`, typed errors → HTTP; ingestion CLI.
- **Infra**: Dockerfile, Helm chart (probes, HPA, PDB, security, ExternalSecret), Tilt,
  Terraform `envs/dev` validated (VPC, EKS 1.33 + Pod Identity, RDS pg16 pgvector, ECR, S3,
  secrets, roles), verified on k3d; Langfuse v4 on k3d (OTLP → ClickHouse proven, cost
  recomputed identical to ours); 10 `docs/infra/` guides (README + 00→09, 09 added on 2026-10-19).
- **Notebooks**: 1 (robust LLM call, 39 cells) and 2 (document → index, 26 cells),
  run in sample mode, in CI with Postgres as a service.
- **First measurement** (`data/results/embeddings_scifact.json`, mteb, SciFact nDCG@10):
  bge-base-en-v1.5 **0.740** (published 0.7404 — zero gap); all-MiniLM-L6-v2 **0.645**
  (< published BM25 0.665); text-embedding-3-small to be produced with a key.
- Tests: 155 offline, 6 on a database, 2 network; mypy strict; pre-commit hooks aligned.

## Remaining in phase 1 (Christophe's actions)

1. Review phase 1 on `main` (merged on 2026-10-16 without a formal review of PR #3);
   the reading order, blocks 0 to 5, is in `docs/reading-order.md` (2026-10-20).
2. `.env` with the keys (`.env.example`) → `make ingest-scifact`, `make api` or `tilt up`,
   `make notebooks-full` ("real provider" section of notebook 1, real embeddings and real
   generation of notebook 2), `make bench-embeddings` (adds text-embedding-3-small).
3. Guide 00 (bootstrap, 15 min; eight resources since 2026-10-19, GitHub OIDC role
   included), then the repository variable of guide 09:
   `gh variable set AWS_DEPLOY_ROLE_ARN --body "$(cd infra/terraform/bootstrap && terraform output -raw github_deploy_role_arn)"`,
   then guides 02→05: `make infra-up`, `make cluster-addons`, secrets, `make deploy` or
   `make deploy-trigger` (guide 09) — the API on EKS (≈ $6/day while running, `make infra-down`
   in the evening).
4. **GPU quota** (phase 6, ADR 009: days to weeks). The two requests for 8 vCPU
   (one g6.2xlarge or two g6.xlarge) were sent on 2026-10-20, account 749020018778,
   eu-west-3, status `CASE_OPENED`: AWS opened one support case per request, and the
   answer arrives by email to the account contact.
   - "All G and VT Spot Instance Requests" (`L-3819A6DF`), 10:51.
   - "Running On-Demand G and VT instances" (`L-DB2E81BA`), 10:54, sent by Christophe.

   Read the state of the two cases (read-only, sends nothing to AWS):

   ```bash
   aws service-quotas list-requested-service-quota-change-history --service-code ec2 --region eu-west-3 \
     --query "RequestedQuotas[?contains(QuotaName,'G and VT')].[QuotaName,DesiredValue,Status]" --output table
   ```

   Statuses: `PENDING` → `CASE_OPENED` → `APPROVED` or `DENIED`; `CASE_CLOSED` only means
   the case was closed, so then check the applied value with `list-service-quotas`.

## Current numbers

First number of the testbench (mteb protocol, not our harness yet). Reference points:
BM25 = 0.665 nDCG@10 on SciFact (BEIR paper); embeddings measured on 2026-09-03: bge-base-en-v1.5 0.740 (= published), all-MiniLM-L6-v2 0.645.

## Decisions awaiting a call

- **AWS bootstrap to be applied by Christophe** following `docs/infra/00-bootstrap.md`
  (existing AWS account, eu-west-3 region, no budget and no state bucket to date — the
  `eks-foundations-terraform-chris` bucket belongs to another project, we do not touch it).
  The `envs/dev` modules and the deployment workflow (guide 09) depend on it.
- **PD-5 to update in the program** (`~/Roadmaps/program`, `docs/07-decisions.md` and
  `docs/02-shared-rules.md`): its exception "roadmap-ai-engineer is a French brief … stays as
  written" no longer holds since ADR 010; to be done from a program session.
- Actual data governance constraints: unknown to date, mechanism built in phase 1 with a
  permissive policy on public data; to be hardened when they become clearer
  (`docs/decisions.md`, 2026-09-03).
- Post-phase-10 extension candidate (noted on 2026-09-01, GO/NO-GO decision **after
  phase 5**, not before): the LLMOps data loop — phase 5 traces → sampling → labeling by
  the calibrated judge (phase 2) → curation → extension of the golden set and of the LoRA
  training set (phase 6). No "data pipeline" phase in the data engineering sense
  (Kafka/Spark/dbt/CDC): outside the positioning, static data, duplicate of phase 3 — see
  `JOURNAL.md` 2026-09-01.

## Amendments recorded for upcoming phases (2026-10-15)

No separate "pipeline" roadmap (`JOURNAL.md` 2026-10-15 and 2026-09-01). The three added
obligations (Dagster as a named deliverable in phase 3, queue + worker in phase 5, run
manifest in 5B and 6) are integrated into `docs/roadmap/phase-3.md`, `phase-5.md`,
`phase-5b.md` and `phase-6.md`.

## Amendments of 2026-10-19 (resumption audit, ADR 009)

AWS services entry rule (`CLAUDE.md` §4) and its first applications: Bedrock Knowledge Bases
as a comparison arm in notebook 4 of phase 3; SQS (abstraction with two implementations,
Postgres `SKIP LOCKED` locally), ADOT, Karpenter and Cost Anomaly Detection in phase 5; GPU
node group on the existing EKS as the second measured target of phase 6; Guardrails
(phase 7) and AgentCore (phase 4) as options. The CV leaves phase 8 (held by the program).
A single `dev` environment. Deployment via GitHub Actions and OIDC (guide 09). Notebooks 1
and 2 run on `claude-sonnet-5-5`.

## Brief organization (2026-10-16)

`CLAUDE.md` keeps only the working contract; roadmap in `docs/roadmap/` (one file per
phase), decision log in `docs/decisions.md`. Session resumption: `STATE.md`, `JOURNAL.md`,
`docs/decisions.md`, last 3 ADRs, current phase file.

## Notebook layout (2026-10-19)

One subfolder per phase: `notebooks/phase-N/NN_slug.ipynb` (`phase-0/00_guided_tour`,
`phase-1/01_robust_llm_call`, `phase-1/02_document_to_index`). CI and `make notebooks-ci`
run the whole `notebooks/` folder; paths and `.env` are anchored on `find_repo_root()`.

## Language (2026-10-20)

Everything in English, no French anywhere in the repository (ADR 010, `CLAUDE.md` §2.B.5):
prose, notebooks, docstrings, messages, test data, prompts (`chat_answer` and
`structured_output_*` at v2, refusal sentinel in English) and file names. Commit messages
before 2026-10-20 stay in French in the history.

## Recorded constraints

- API keys: OpenAI, Anthropic, OpenRouter (Mistral via OpenRouter).
- Budget: no cap a priori; AWS alert at 55 USD/month; each cost item documented.
- Pace: no calendar, the brief's "weeks" are units of effort.
