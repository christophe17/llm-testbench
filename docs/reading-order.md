# Testbench reading order

> What to read, phase by phase, in order: the roadmap file, the notebooks, and the infra guides
> at the point where a run needs them. The `src/` modules are not listed: each notebook shows
> the ones it uses (`inspect.getsource`). What is done or not is in `STATE.md`.
>
> Legend: ✅ exists · ⏳ to come, name given by the roadmap.

Start with the overview: [roadmap/README.md](roadmap/README.md).

## Phase 0 — Foundations ✅

1. Roadmap — [phase-0.md](roadmap/phase-0.md)
2. Notebook — [00 guided tour](../notebooks/phase-0/00_guided_tour.ipynb): corpus, queries,
   qrels, nDCG, the datasets

## Phase 1 — Production skeleton ✅

1. Roadmap — [phase-1.md](roadmap/phase-1.md)
2. Notebook — [01 robust LLM call](../notebooks/phase-1/01_robust_llm_call.ipynb): nothing to
   install, sample mode
3. Infra guide — [01 local dev k3d](infra/01-local-dev-k3d.md): `make k3d-up`, the pgvector
   database notebook 2 needs
4. Notebook — [02 from document to index](../notebooks/phase-1/02_document_to_index.ipynb)
5. Infra guide — [07 observability](infra/07-observability.md): `make langfuse-up`, where the
   traces of notebooks 1 and 2 go

Then the cloud (AWS, ≈ $6/day while running). Can wait until the end of phase 2, must be done
before phase 3:

6. Infra guide — [00 bootstrap](infra/00-bootstrap.md)
7. Infra guide — [08 costs](infra/08-costs.md), before turning anything on
8. Infra guide — [02 network](infra/02-network-vpc.md)
9. Infra guide — [03 EKS](infra/03-eks.md)
10. Infra guide — [04 RDS pgvector](infra/04-rds-pgvector.md)
11. Infra guide — [05 secrets](infra/05-secrets.md)
12. Infra guide — [06 Helm chart](infra/06-helm-chart-api.md)
13. Infra guide — [09 GitHub OIDC deployment](infra/09-github-oidc-deployment.md)

## Phase 2 — Evaluation ⏳

1. Roadmap — [phase-2.md](roadmap/phase-2.md)
2. Notebook — `phase-2/01_*`: measuring a RAG, why end-to-end metrics hide the real problem
3. Notebook — `phase-2/02_*`: LLM-as-judge, calibrate it or do not use it
4. Notebook — `phase-2/03_*`: contamination, why your good scores may be lying
5. Notebook — `phase-2/04_*`: building a golden set from nothing, at small scale

## Phase 3 — Advanced RAG ⏳

Requires the phase 1 cloud guides.

1. Roadmap — [phase-3.md](roadmap/phase-3.md)
2. Notebook — `phase-3/01_*`: why hybrid search saves acronyms and jargon
3. Notebook — `phase-3/02_*`: the duel of chunking strategies on raw documents
4. Notebook — `phase-3/03_*`: query transformation, when it helps, when it costs for nothing
5. Notebook — `phase-3/04_*`: our pipeline against LlamaIndex and Bedrock Knowledge Bases
6. Infra guide — ⏳ the orchestrator on the cluster
7. Notebook — `phase-3/05_*`: the experiment matrix, regenerating a hundred indexes

## Phase 4 — Multi-source agents ⏳

1. Roadmap — [phase-4.md](roadmap/phase-4.md)
2. Notebook — `phase-4/01_*`: an agent without a framework, then the same agent on four
   frameworks
3. Notebook — `phase-4/02_*`: text-to-SQL, from the schema to the safe query
4. Notebook — `phase-4/03_*`: tools, APIs and side effects
5. Notebook — `phase-4/04_*`: structured data and images, extracting without hallucinating
6. Notebook — `phase-4/05_*`: multi-source routing and contradictory sources
7. Notebook — `phase-4/06_*`: evaluating an agent, trajectories, execution, extraction
8. Notebook — `phase-4/07_*`: agent memory, what to retain, where, at what cost

## Phase 5 — LLMOps ⏳

1. Roadmap — [phase-5.md](roadmap/phase-5.md)
2. Infra guides, reread — [07 observability](infra/07-observability.md) and
   [09 GitHub OIDC deployment](infra/09-github-oidc-deployment.md): the foundation
3. Notebook — `phase-5/01_*`: anatomy of a trace, and where the milliseconds come from
4. Infra guide — ⏳ ADOT vs vanilla collector
5. Notebook — `phase-5/02_*`: the cost model, from the token to the price per user
6. Infra guides — ⏳ Cost Anomaly Detection, Karpenter
7. Notebook — `phase-5/03_*`: detecting a quality regression in production without labels
8. Infra guide — ⏳ SQS

## Phase 5B — The bridge ⏳

1. Roadmap — [phase-5b.md](roadmap/phase-5b.md)
2. Notebook — `phase-5b/01_*`: choosing between an XGBoost and an LLM, the answer is a table

## Phase 6 — Inference and open models ⏳

1. Roadmap — [phase-6.md](roadmap/phase-6.md)
2. Infra guide — ⏳ the GPU target (ephemeral specialized provider, or node group on the
   existing EKS)
3. Notebook — `phase-6/01_*`: what vLLM really does under the hood
4. Notebook — `phase-6/02_*`: the real quality cost of quantization
5. Notebook — `phase-6/03_*`: self-host vs API, the full calculation

## Phase 7 — Residual security and compliance ⏳

1. Roadmap — [phase-7.md](roadmap/phase-7.md)
2. Notebooks — decided at the phase plan; the roadmap names none

## Phase 8 — Packaging ⏳

1. Roadmap — [phase-8.md](roadmap/phase-8.md): read from phase 2 on, as the phases go

## Phase 9 — Voice ⏳

1. Roadmap — [phase-9.md](roadmap/phase-9.md)
2. Notebook — `phase-9/01_*`: where the latency of a voice agent comes from
3. Notebook — `phase-9/02_*`: evaluating an agent you listen to

## Phase 10 — Browser and computer use ⏳ (if GO after phase 9)

1. Roadmap — [phase-10.md](roadmap/phase-10.md)
2. Notebook — `phase-10/01_*`: an agent that clicks

---

At each phase closing (`CLAUDE.md` §3, "Traces" step), the phase's ⏳ items become links.
