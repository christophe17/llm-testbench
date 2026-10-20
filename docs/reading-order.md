# Testbench reading order

> What to read, phase by phase: the roadmap file, the notebooks, the infra guides. Inside a
> phase, read in that order; an infra guide comes when a run needs it. The `src/` modules are
> not listed: each notebook shows the ones it uses (`inspect.getsource`). What is done or not
> is in `STATE.md`.
>
> Legend: ✅ exists · ⏳ to come, name given by the roadmap.

Start with the overview: [roadmap/README.md](roadmap/README.md).

## Phase 0 — Foundations ✅

- **Roadmap**: [phase-0.md](roadmap/phase-0.md)
- **Notebook**: [00 — guided tour](../notebooks/phase-0/00_guided_tour.ipynb)
- **Infra**: none

## Phase 1 — Production skeleton ✅

- **Roadmap**: [phase-1.md](roadmap/phase-1.md)
- **Notebooks**:
  1. [01 — robust LLM call](../notebooks/phase-1/01_robust_llm_call.ipynb)
  2. [02 — from document to index](../notebooks/phase-1/02_document_to_index.ipynb)
- **Infra, local** (needed for notebook 2 and the traces):
  [01 — local dev k3d](infra/01-local-dev-k3d.md) →
  [07 — observability](infra/07-observability.md)
- **Infra, cloud** (AWS, ≈ $6/day while running; before phase 3), in run order:
  [00 — bootstrap](infra/00-bootstrap.md) → [08 — costs](infra/08-costs.md) →
  [02 — network](infra/02-network-vpc.md) → [03 — EKS](infra/03-eks.md) →
  [04 — RDS pgvector](infra/04-rds-pgvector.md) → [05 — secrets](infra/05-secrets.md) →
  [06 — Helm chart](infra/06-helm-chart-api.md) →
  [09 — GitHub OIDC deployment](infra/09-github-oidc-deployment.md).
  Index with the cost of each: [infra/README.md](infra/README.md).

## Phase 2 — Evaluation ⏳

- **Roadmap**: [phase-2.md](roadmap/phase-2.md)
- **Notebooks**:
  1. `phase-2/01_*` — measuring a RAG: why end-to-end metrics hide the real problem
  2. `phase-2/02_*` — LLM-as-judge: calibrate it or do not use it
  3. `phase-2/03_*` — contamination: why your good scores may be lying
  4. `phase-2/04_*` — building a golden set from nothing, at small scale
- **Infra**: none (offline phase)

## Phase 3 — Advanced RAG ⏳

- **Roadmap**: [phase-3.md](roadmap/phase-3.md)
- **Notebooks**:
  1. `phase-3/01_*` — why hybrid search saves acronyms and jargon
  2. `phase-3/02_*` — the duel of chunking strategies on raw documents
  3. `phase-3/03_*` — query transformation: when it helps, when it costs for nothing
  4. `phase-3/04_*` — our pipeline against LlamaIndex and Bedrock Knowledge Bases
  5. `phase-3/05_*` — the experiment matrix: regenerating a hundred indexes
- **Infra**: ⏳ the orchestrator on the cluster; the cloud guides of phase 1 must be done

## Phase 4 — Multi-source agents ⏳

- **Roadmap**: [phase-4.md](roadmap/phase-4.md)
- **Notebooks**:
  1. `phase-4/01_*` — an agent without a framework, then the same agent on four frameworks
  2. `phase-4/02_*` — text-to-SQL, from the schema to the safe query
  3. `phase-4/03_*` — tools, APIs and side effects
  4. `phase-4/04_*` — structured data and images: extracting without hallucinating
  5. `phase-4/05_*` — multi-source routing and contradictory sources
  6. `phase-4/06_*` — evaluating an agent: trajectories, execution, extraction
  7. `phase-4/07_*` — agent memory: what to retain, where, at what cost
- **Infra**: none planned

## Phase 5 — LLMOps ⏳

- **Roadmap**: [phase-5.md](roadmap/phase-5.md)
- **Notebooks**:
  1. `phase-5/01_*` — anatomy of a trace, and where the milliseconds come from
  2. `phase-5/02_*` — the cost model, from the token to the price per user
  3. `phase-5/03_*` — detecting a quality regression in production without labels
- **Infra**: foundation [07 — observability](infra/07-observability.md) and
  [09 — GitHub OIDC deployment](infra/09-github-oidc-deployment.md); ⏳ ADOT vs vanilla
  collector, SQS, Karpenter, Cost Anomaly Detection

## Phase 5B — The bridge ⏳

- **Roadmap**: [phase-5b.md](roadmap/phase-5b.md)
- **Notebook**: `phase-5b/01_*` — choosing between an XGBoost and an LLM, the answer is a table
- **Infra**: none

## Phase 6 — Inference and open models ⏳

- **Roadmap**: [phase-6.md](roadmap/phase-6.md)
- **Notebooks**:
  1. `phase-6/01_*` — what vLLM really does under the hood
  2. `phase-6/02_*` — the real quality cost of quantization
  3. `phase-6/03_*` — self-host vs API, the full calculation
- **Infra**: ⏳ the GPU target (ephemeral specialized provider, or node group on the existing EKS)

## Phase 7 — Residual security and compliance ⏳

- **Roadmap**: [phase-7.md](roadmap/phase-7.md)
- **Notebooks**: decided at the phase plan; the roadmap names none
- **Infra**: none planned

## Phase 8 — Packaging ⏳

- **Roadmap**: [phase-8.md](roadmap/phase-8.md) (read from phase 2 on, as the phases go)
- **Notebooks**: none
- **Infra**: none

## Phase 9 — Voice ⏳

- **Roadmap**: [phase-9.md](roadmap/phase-9.md)
- **Notebooks**:
  1. `phase-9/01_*` — where the latency of a voice agent comes from
  2. `phase-9/02_*` — evaluating an agent you listen to
- **Infra**: none planned

## Phase 10 — Browser and computer use ⏳ (if GO after phase 9)

- **Roadmap**: [phase-10.md](roadmap/phase-10.md)
- **Notebook**: `phase-10/01_*` — an agent that clicks
- **Infra**: none planned

---

At each phase closing (`CLAUDE.md` §3, "Traces" step), the phase's ⏳ items become links.
