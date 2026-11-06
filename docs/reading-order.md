# Testbench reading order

> What to read, phase by phase, in order: the roadmap file, the notebooks, and the infra guides
> at the point where a run needs them. The `src/` modules are not listed: each notebook links
> to the functions and classes it uses (file and line), and the class diagrams of `src/`, one
> per concept, are in [diagrams/README.md](diagrams/README.md). What is done or not is in
> `STATE.md`.
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
3. Infra guide — [01 local dev k3d](infra/01-local-dev-k3d.md): `make k3d-create` + `make tilt-db`, the pgvector
   database notebook 2 needs; its companion [01b Tilt crash course](infra/01b-tilt-crash-course.md)
   explains what Tilt does behind those two commands
4. Notebook — [02 from document to index](../notebooks/phase-1/02_document_to_index.ipynb)
   - Side notebook — [02b MTEB crash course](../notebooks/phase-1/02b_mteb_crash_course.ipynb):
     the benchmark and the library behind notebook 2's table, and what the roadmap takes from
     them; optional, `mteb` installed (`uv sync --group bench`)
5. Infra guide — [06 Helm chart](infra/06-helm-chart-api.md): the API's chart (probes, HPA,
   PDB, resources), rendered and deployed on the local cluster
6. Infra guide — [07 observability](infra/07-observability.md): `make langfuse-up`, self-hosted
   Langfuse receiving the API's traces; no notebook of phases 1 and 2 needs it

The cloud guides written in this phase (00, 02 to 05, 08, 09) are listed at the head of
phase 3, the first phase that runs something on AWS.

## Phase 2 — Evaluation ⏳

The four notebooks exist and run; two of them wait for something only a person can give
(50 labels for the judge, the review of the golden set). They need the local database of
phase 1 (`make tilt-db`), nothing in the cloud, and no API key: their live cells run on
fixtures, their numbers are read from the full runs archived under `data/results/`.

1. Roadmap — [phase-2.md](roadmap/phase-2.md), then the decisions:
   [ADR 011](adr/011-evaluation-harness.md) (the retrieval harness),
   [ADR 012](adr/012-judge-and-calibration.md) (the judge, the spend cap),
   [ADR 013](adr/013-end-to-end-runs.md) (end to end),
   [ADR 014](adr/014-in-house-corpus-and-golden-set.md) (the corpus, the golden set)
2. ✅ Notebook — [01 measuring a RAG](../notebooks/phase-2/01_measuring_a_rag.ipynb): why an
   end-to-end score hides the real problem. Start here: the three others lean on it
3. ✅ Notebook — [02 LLM-as-judge](../notebooks/phase-2/02_llm_as_judge.ipynb): calibrate it
   or do not use it. The method runs end to end on toy answers; the real numbers appear
   after `make eval-annotate` (one hour, yours) and `make eval-calibrate`
4. ✅ Notebook — [03 contamination](../notebooks/phase-2/03_contamination.ipynb): why your
   good scores may be lying. It changes how the numbers of notebook 1 are read
5. ✅ Notebook — [04 building a golden set](../notebooks/phase-2/04_golden_set.ipynb): from
   scratch, small. Then the review itself: `make golden-review` (two to three hours, yours)

## Phase 3 — Advanced RAG ⏳

First the cloud (AWS, ≈ $6/day while running), as one block before `GO PHASE 3`. These guides
were written in phase 1; phases 1 and 2 run nothing on AWS, and phase 3 is the first that does
(Bedrock Knowledge Bases in notebook 4, the orchestrator on the cluster). Guide 00 costs about
€0 a month and creates the budget alert: it can be applied any day before.

1. ✅ Infra guide — [00 bootstrap](infra/00-bootstrap.md)
2. ✅ Infra guide — [08 costs](infra/08-costs.md), before turning anything on
3. ✅ Infra guide — [02 network](infra/02-network-vpc.md)
4. ✅ Infra guide — [03 EKS](infra/03-eks.md)
5. ✅ Infra guide — [04 RDS pgvector](infra/04-rds-pgvector.md)
6. ✅ Infra guide — [05 secrets](infra/05-secrets.md)
7. ✅ Infra guide — [09 GitHub OIDC deployment](infra/09-github-oidc-deployment.md)
8. Roadmap — [phase-3.md](roadmap/phase-3.md)
9. Notebook — `phase-3/01_*`: why hybrid search saves acronyms and jargon
10. Notebook — `phase-3/02_*`: the duel of chunking strategies on raw documents
11. Notebook — `phase-3/03_*`: query transformation, when it helps, when it costs for nothing
12. Notebook — `phase-3/04_*`: our pipeline against LlamaIndex and Bedrock Knowledge Bases
13. Infra guide — ⏳ the orchestrator on the cluster
14. Notebook — `phase-3/05_*`: the experiment matrix, regenerating a hundred indexes

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
