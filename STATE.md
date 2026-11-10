# STATE

> Snapshot of the project state. Updated at each work session.
> Detailed history in `JOURNAL.md`, decisions in `docs/adr/`.

## Current phase

**Phase 2 — Evaluation: in progress** since `GO PHASE 2` (2026-11-05). Steps 1 (retrieval
harness) and 2 (gate, comparison, HTML report) are built and measured. Step 3 is built
except for what needs a calibrated judge: generation is measured on the gold context and
end to end on HotpotQA and QASPER, closed book on three datasets, and **the calibration
waits for Christophe's 50 labels** (`make eval-annotate`). Step 4 is built up to the
review: the in-house corpus is selected and downloaded, 83 golden questions are drafted
and checked, and **the golden set waits for Christophe's review** (`make golden-review`).
The four notebooks of the phase exist and run in CI; two of them have an empty place for
the numbers those two tasks will produce. Budget: hard cap $10, $4.81 spent
(`data/results/spend.jsonl`). Decisions in ADR 011 to ADR 014.

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
  run in sample mode, in CI with Postgres as a service; side notebook 2b (MTEB crash course,
  29 cells, 2026-11-04), optional, runs in CI without `mteb`.
- **First measurement** (`data/results/embeddings_scifact.json`, mteb, SciFact nDCG@10):
  bge-base-en-v1.5 **0.740** (published 0.7404 — zero gap); all-MiniLM-L6-v2 **0.645**
  (< published BM25 0.665); text-embedding-3-small to be produced with a key. **2026-11-04**
  (notebook 2b): BM25 through `mteb/baseline-bm25s` **0.686** (the paper's Anserini: 0.665;
  `data/results/bm25_scifact.json`); bge-base-en-v1.5 without its query instruction 0.738.
- Tests: 162 offline, 6 on a database, 2 network; mypy strict; pre-commit hooks aligned.
- **Re-ingestion done on 2026-11-05**: the index the API serves
  (`scifact-recursive-oai-small`) was rebuilt by the evaluation suite with `title + " " +
  text` (10,460 chunks, $0.038).

## Done in phase 2 (2026-11-05, ADR 011)

- **Retrieval harness**: metrics recall@k, precision@k, MRR@k, nDCG@k (`trec_eval`
  conventions, cross-checked against `pytrec_eval`); bootstrap intervals and paired
  comparison of two runs; `Retriever` contract at the document level, BM25 (`bm25s`) and
  dense (pgvector, best chunk per document, exact or HNSW); open embedding models in
  process (backend `hf`); NFCorpus and FiQA loaders; suites and arms in
  `config/eval_suites.toml`, an arm building the index it reads; run record archived under
  `data/results/runs/` and saved to Postgres (`eval_runs`, `eval_query_results`).
- **Industrialization**: `make eval` (run, archive, difference with the previous archive,
  report), `make eval-report` (HTML, `build/eval/`), `make eval-compare`, `make eval-gate`
  in sample mode as a `pre-push` hook and a CI step, `make eval-gate-update`.
- Ingestion reads the state of an index in two queries: an up-to-date index is verified in
  seconds.

- **Generation and judge** (ADR 012): QA dataset type and SQuAD 2.0 loader; generation on
  gold passages through the API's own prompt and parser, scored without a judge (correct
  refusal, over-refusal, citations, reference answer) and asked several times to measure
  what changes between runs; the judge (two rubrics, yes or no, reasons first); the
  calibration set, the terminal annotation tool, Cohen's kappa; a spend ledger with a cap.

- **End to end** (ADR 013): one generation runner for three contexts, the gold passages,
  the chunks the API's document source retrieves, or nothing (closed book); each
  end-to-end answer records whether its gold passages were retrieved, and failures are
  split between the search and the generator. HotpotQA as a pool of 1,000 questions and
  9,789 paragraphs; QASPER answers and evidence, searched inside the question's paper.
  Bias probes of the judge (`make eval-bias`), to run after the calibration.
- **Notebooks** (`notebooks/phase-2/`): 01 measuring a RAG (33 cells), 02 LLM-as-judge
  (20), 03 contamination (18), 04 building a golden set (23). Live cells on fixtures with
  scripted models, numbers read from the archived runs; reading order in
  `docs/reading-order.md`. Each opens with "Before you start" and defines every notion
  before using it, the words of the earlier notebooks included (2026-11-10).
- **Two defects of phase 1 found by the end-to-end runs and fixed**: ingestion did not
  refresh the planner's statistics after a load (a search of 22 seconds on a fresh index,
  5 ms after `ANALYZE`); the output cap of an answer was sized for its visible text while
  the generator reasons first (answers cut or empty, silently). One cap now, shared by the
  API and the harness, and every run reports its share of cut answers.

- **In-house corpus and golden set** (ADR 014): 200 arXiv papers under CC BY 4.0, first
  submitted after every model used was released, selected for what breaks a PDF
  extraction (tables, footnotes, formulas); a versioned manifest, the documents in the
  local cache (`make corpus-download`); a reference text per document from arXiv's HTML
  rendering; one naive PDF extractor (`ingest/pdf.py`). Golden set tooling: drafting with
  quotes checked word for word, two automatic checks of the drafts, a terminal review, a
  frozen set with a changelog (`make golden-draft`, `golden-probe`, `golden-review`,
  `golden-freeze`, `golden-status`). 83 drafts on 30 documents are waiting.

## Remaining in phase 2

1. **Christophe: label the 50 calibration items**, `make eval-annotate`, about one hour,
   resumable. Then `make eval-calibrate` (about $0.40) gives the kappa of both judges; the
   judged baseline, the bias probes (`make eval-bias`) and a rubric for correctness
   against the reference answer (QASPER needs it) follow.
2. **Christophe: review the 83 drafted questions**, `make golden-review`, two to three
   hours, resumable (each draft shows the link to its paper on arXiv; nothing to
   download); then `make golden-freeze VERSION=v1 SUMMARY="..."`. The arms that run the
   golden set on the naive text and on the reference text follow, and need the corpus
   (`make corpus-download`, 20 minutes, 1.1 GB).
3. After 1 and 2: the judged baseline, the golden set's arms, the numbers of notebooks 2
   and 4, the README, the phase closing and its debrief.
4. Three class diagrams of phase 2 are written in `docs/diagrams/` (11 to 13) and pass
   `tests/test_diagrams.py`; they are not committed, because the directory itself is not
   yet (it belongs to work in progress in another session). Not rendered: only checked
   against the code.

**Local database recreated on 2026-11-05** (`JOURNAL.md`: a commit made Tilt delete the
namespace). The suite rebuilt its indexes; the QASPER index of notebook 2
(`qasper-nb2-oai-small`) is rebuilt by notebook 2 at its next full run; the `eval_runs`
history restarts from the rerun. Commits are now made from a clean worktree.

## Remaining in phase 1 (Christophe's actions)

1. Review phase 1 on `main` (merged on 2026-10-16 without a formal review of PR #3);
   what to read for phases 0 and 1 is in `docs/reading-order.md`.
2. `.env` with the keys (`.env.example`) → `make ingest-scifact`, `make api` or `tilt up`,
   `make notebooks-full` ("real provider" section of notebook 1, real embeddings and real
   generation of notebook 2), `make bench-embeddings` (adds text-embedding-3-small).
3. Guide 00 (bootstrap, 15 min; eight resources since 2026-10-19, GitHub OIDC role
   included), then the repository variable of guide 09:
   `gh variable set AWS_DEPLOY_ROLE_ARN --body "$(cd infra/terraform/bootstrap && terraform output -raw github_deploy_role_arn)"`,
   then guides 02→05: `make infra-up`, `make cluster-addons`, secrets, `make deploy` or
   `make deploy-trigger` (guide 09) — the API on EKS (≈ $6/day while running, `make infra-down`
   in the evening). Scheduled as one block before `GO PHASE 3` (`docs/reading-order.md`,
   2026-11-06); guide 00 can be applied any day before.
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

Through our harness since 2026-11-05 (SciFact test, 300 queries, nDCG@10 with its 95%
bootstrap interval; `data/results/runs/retrieval-baseline/`, table in `JOURNAL.md`):

- Reproductions: BM25 **0.686** (0.686 through `mteb`; the BEIR paper's Anserini: 0.665),
  bge-base-en-v1.5 on whole documents with exact search **0.740** (model card: 0.740),
  text-embedding-3-small **0.732** (0.731 through `mteb`). NFCorpus, graded judgments: BM25
  0.321 (paper: 0.325), bge-base-en-v1.5 0.374 (model card: 0.374).
- **Phase 1 system as built** (text-embedding-3-small, chunks 1000/200, HNSW defaults):
  **0.727** [0.684, 0.767], recall@100 0.908; against BM25 +0.041 [+0.004, +0.076].
- Same index searched exactly, or with `ef_search = 400`: 0.735, recall@100 0.963. The HNSW
  default list of 40 candidates costs 5.5 points of recall@100 (significant) and nothing
  significant on nDCG@10. Two builds of the same HNSW index scored 0.730 and 0.727.
- On 300 queries an nDCG@10 is known to about ±0.04: bge-base against text-embedding-3-small
  (+0.008) and chunks against whole documents (+0.002) are not significant differences.
- Latency, p50, one query at a time from the laptop: BM25 0.2 ms; dense on the OpenAI model
  230 ms, of which 220 ms is the API call embedding the question and 34 ms the HNSW search
  (95 ms with `ef_search = 400`, 138 ms exact); bge-base in process 20 ms + 42 ms exact.

Earlier, through `mteb` (phase 1): all-MiniLM-L6-v2 0.645.

FiQA (648 queries, a corpus of 57,638 documents): BM25 0.251 (paper: 0.236),
bge-base-en-v1.5 on whole documents 0.406 (model card: 0.407); the system as built **0.417**
[0.389, 0.445] with recall@100 0.642, against 0.428 and 0.764 for the same index searched
exactly: the HNSW default costs 12 points of recall@100 there.

Generation on gold context (SQuAD 2.0, 100 questions, half unanswerable,
`claude-sonnet-5-5`; `data/results/runs/generation-baseline/`): correct refusal **0.74**
[0.62, 0.86], over-refusal **0.04** [0.00, 0.10], reference answer present 0.92, an excerpt
cited in 100% of the answers given and none invented, including on the 26% of unanswerable
questions that were answered. Asked three times, the refusal flips on 8% of 50 questions.

End to end (`data/results/runs/end-to-end/`, 100 questions per arm, five chunks to the
generator):

- **HotpotQA** (two paragraphs needed per question): reference answer given **0.57**
  [0.47, 0.67] end to end against 0.85 on the gold context. Both gold paragraphs are
  retrieved for 60% of the questions; of the 43 failures, 33 have a paragraph missing and
  29 of those are refusals. Retrieval alone on the pool: recall@5 0.806, nDCG@10 0.816
  (BM25: 0.737 and 0.756).
- **QASPER** (one paper per question): correct refusal on unanswerable questions **0.74**
  [0.62, 0.86]; all gold paragraphs retrieved for 54% of the answerable ones. "Reference
  answer given" is 0.28 even on the gold evidence: not a usable metric on free-form
  answers, a judge is needed.
- **Closed book** (`data/results/runs/contamination/`): with no document, the generator
  gives the reference answer on **53%** of the HotpotQA questions, 38% of SQuAD's, 0% of
  QASPER's. Of the 57 HotpotQA questions the system gets right end to end, 38 are ones
  the model answers alone.

## Decisions awaiting a call

- **Phase 2**: Ragas as the one third-party evaluator measured on the calibration items
  was proposed with the plan and not answered; it costs a few cents and a dependency in
  the `bench` group. Decided on 2026-11-05: lean budget under a $10 cap, judge
  `gpt-5.6-luna`, arXiv CC BY 4.0 corpus (`docs/decisions.md`).
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

## Amendments of 2026-11-05 (phase 3)

Three measured arms added to `docs/roadmap/phase-3.md`: SPLADE next to BM25 in the hybrid
block, a LambdaMART learning-to-rank step between RRF and the cross-encoder, quantized vectors
with exact rescoring as a cost arm; ColBERT excluded and documented as not done
(`docs/decisions.md`, 2026-11-05).

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
