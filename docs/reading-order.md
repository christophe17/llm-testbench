# Testbench reading order

> In which order to read this repository to study it, from phase 0 to phase 10. Written on
> 2026-10-20, when resuming the built phase 1. It is a reading map, not a state: what is
> done or not is in `STATE.md`.

## Principles

- **One block, one sitting.** Each block says what it requires: nothing, a local Postgres,
  keys, an AWS cluster. Blocks with no requirement come first.
- **The order within a block is always the same**: the ADR that justifies the structure
  → the notebook, run in sample mode → the `src/` modules at the moment the notebook
  displays them (`inspect.getsource`) → the module's test when a contract remains unclear → the
  infra guide when a run requires it.
- **Phases not yet built** list the deliverables that `docs/roadmap/phase-N.md` names,
  with the roadmap's notebook numbers (`notebooks/phase-N/NN_slug.ipynb`). The exact paths
  are written here at the phase closing (`CLAUDE.md` §3 protocol, "Traces" step).
  Nothing marked ⏳ is to be looked for in the repository before then.
- Legend: ✅ exists · ⏳ to come, name given by the roadmap.

## Resumption ritual, at every return

Before any block, in this order: [STATE.md](../STATE.md) → latest entries of
[JOURNAL.md](../JOURNAL.md) → [decisions.md](decisions.md), the lines since your last
session → the ADRs those lines cite → `docs/roadmap/phase-N.md` of the current phase.
This is the brief's session resumption protocol, applied to you too.

---

## Block 0 — What changed during the break (✅ · 30 min · nothing to install)

1. [decisions.md](decisions.md), lines of 2026-10-19.
2. [ADR 009](adr/009-single-environment-oidc-aws-services.md): a single environment,
   OIDC deployment, AWS services entry rule.
3. [STATE.md](../STATE.md), "Remaining" section. The GPU quota request is launched as early as
   this block: it takes days to weeks and phase 6 depends on it.

## Block 1 — Phase 0, the vocabulary (✅ · one sitting · nothing to install)

4. [ADR 001](adr/001-datasets.md) (the selected datasets) and
   [ADR 004](adr/004-loader-interface.md) (the loader interface), short.
5. [Notebook 0](../notebooks/phase-0/00_guided_tour.ipynb): corpus, queries, qrels,
   nDCG, SciFact, the fifteen datasets. In part 4, read alongside
   [eval/types.py](../src/llm_testbench/eval/types.py),
   [eval/loaders/base.py](../src/llm_testbench/eval/loaders/base.py),
   [eval/loaders/beir.py](../src/llm_testbench/eval/loaders/beir.py) and
   [datasets-verification-2026-08-26.md](datasets-verification-2026-08-26.md).
6. [ADR 003](adr/003-code-conventions.md): how the code is written, typed and tested, to read
   once before opening `src/`.

## Block 2 — Phase 1, the LLM layer (✅ · one to two sittings · nothing to install)

7. [ADR 006](adr/006-llm-layer-and-governance.md) first: it justifies the whole structure.
8. [Notebook 1](../notebooks/phase-1/01_robust_llm_call.ipynb), in sample mode.
   Modules in the order of its part 3:
   - 3.1 the neutral, governed request:
     [llm/types.py](../src/llm_testbench/llm/types.py),
     [llm/governance.py](../src/llm_testbench/llm/governance.py),
     [llm/registry.py](../src/llm_testbench/llm/registry.py), with
     [config/llm_backends.toml](../config/llm_backends.toml) and
     [config/governance_policy.toml](../config/governance_policy.toml);
   - 3.2 the translation to the SDK and the typed errors:
     [llm/provider.py](../src/llm_testbench/llm/provider.py),
     [llm/providers/anthropic.py](../src/llm_testbench/llm/providers/anthropic.py),
     [llm/providers/openai_compatible.py](../src/llm_testbench/llm/providers/openai_compatible.py),
     [llm/errors.py](../src/llm_testbench/llm/errors.py);
   - 3.3 retry, circuit breaker, timeout:
     [llm/resilience.py](../src/llm_testbench/llm/resilience.py);
   - 3.4 budget, cache, governance:
     [llm/budget.py](../src/llm_testbench/llm/budget.py),
     [llm/cache.py](../src/llm_testbench/llm/cache.py),
     [llm/cost.py](../src/llm_testbench/llm/cost.py) with
     [config/llm_pricing.toml](../config/llm_pricing.toml);
   - 3.5 the facade, where the order of the links in the chain is the contract:
     [llm/client.py](../src/llm_testbench/llm/client.py);
   - 4.7 structured output:
     [llm/structured.py](../src/llm_testbench/llm/structured.py),
     [llm/prompts.py](../src/llm_testbench/llm/prompts.py),
     [prompts/structured_output_instruction.md](../prompts/structured_output_instruction.md),
     [prompts/structured_output_repair.md](../prompts/structured_output_repair.md);
   - 4.1 and 4.8 the trace and streaming:
     [obs/tracing.py](../src/llm_testbench/obs/tracing.py);
   - all of part 4, the simulator that brings down each link:
     [llm/testing.py](../src/llm_testbench/llm/testing.py).
9. When a behavior remains unclear, the module's test is the shortest contract:
   [tests/llm/](../tests/llm/), for example
   [test_resilience.py](../tests/llm/test_resilience.py).

## Block 3 — Phase 1, ingestion and the first measurement (✅ · one sitting · local Postgres)

10. [Guide 01](infra/01-local-dev-k3d.md), `make k3d-up`: notebook 2 needs a pgvector
    database.
11. [ADR 007](adr/007-sources-ingestion-pgvector.md).
12. [Notebook 2](../notebooks/phase-1/02_document_to_index.ipynb), in sample mode.
    Modules in the order of its part 3:
    - 3.1 parsing: [sources/types.py](../src/llm_testbench/sources/types.py),
      [ingest/parsing.py](../src/llm_testbench/ingest/parsing.py),
      [eval/loaders/qasper.py](../src/llm_testbench/eval/loaders/qasper.py);
    - 3.2 chunking: [ingest/chunking.py](../src/llm_testbench/ingest/chunking.py);
    - 3.3 embeddings: [llm/embeddings.py](../src/llm_testbench/llm/embeddings.py);
    - 3.4 storage: [ingest/store.py](../src/llm_testbench/ingest/store.py);
    - 3.5 pipeline: [ingest/pipeline.py](../src/llm_testbench/ingest/pipeline.py),
      [ingest/cli.py](../src/llm_testbench/ingest/cli.py);
    - part 4, from retrieval to the cited answer:
      [sources/documents.py](../src/llm_testbench/sources/documents.py),
      [generation/answer.py](../src/llm_testbench/generation/answer.py),
      [prompts/chat_answer.md](../prompts/chat_answer.md), then the API:
      [app/schemas.py](../src/llm_testbench/app/schemas.py),
      [app/chat.py](../src/llm_testbench/app/chat.py),
      [app/sse.py](../src/llm_testbench/app/sse.py),
      [app/main.py](../src/llm_testbench/app/main.py);
    - part 5, three embeddings against the literature:
      [eval/embeddings_bench.py](../src/llm_testbench/eval/embeddings_bench.py) and the
      archived result `data/results/embeddings_scifact.json`.
13. [Guide 07](infra/07-observability.md), `make langfuse-up` (Docker VM at 12 GB): that is
    where the traces that the two notebooks just emitted go.
14. Reference tests: [tests/ingest/](../tests/ingest/),
    [tests/generation/test_answer.py](../tests/generation/test_answer.py),
    [tests/app/test_api.py](../tests/app/test_api.py).

## Block 4 — Phase 1, full runs (✅ · keys required)

15. `.env` from `.env.example` (OpenAI, Anthropic, OpenRouter), then in order:

    ```bash
    make ingest-scifact
    make notebooks-full      # "real provider" section of 1, real embeddings and generation of 2
    make bench-embeddings    # adds text-embedding-3-small to the notebook 2 table
    ```

16. Reread part 7 of notebook 1 (cost, prompt caching) and part 5 of notebook 2
    with the real numbers, and compare them to `STATE.md` "Current numbers".

## Block 5 — Phase 1, the cloud infra (✅ · AWS · ≈ $6/day while running)

The guides are read in the order in which they are run; the [index](infra/README.md) gives the
cost of each one. This block can wait until the end of phase 2, which is offline; it must be
done before phase 3 (Bedrock Knowledge Bases as a comparison arm, experiment matrix
on the cluster).

17. [Guide 00](infra/00-bootstrap.md): state bucket, budget alert, GitHub OIDC role
    (`make bootstrap-apply`, eight resources, 15 min).
18. [Guide 08](infra/08-costs.md): what each module costs, before turning anything
    on.
19. [Guide 02](infra/02-network-vpc.md) → [03](infra/03-eks.md) →
    [04](infra/04-rds-pgvector.md) → [05](infra/05-secrets.md): `make infra-up`,
    `make cluster-addons`, secrets.
20. [Guide 06](infra/06-helm-chart-api.md): the chart, `make deploy`.
21. [Guide 09](infra/09-github-oidc-deployment.md): the `AWS_DEPLOY_ROLE_ARN` variable
    (command in `STATE.md`), then `make deploy-trigger`.
22. `make infra-down` in the evening.

---

## Block 6 — Phase 2, evaluation (⏳ · central phase)

**Before `GO PHASE 2`**: [roadmap/phase-2.md](roadmap/phase-2.md) in full;
[ADR 008](adr/008-work-on-main.md) for the regression gate (2.7); the one-page plan
I hand in, with its open decisions.

**During the phase, in order**:

23. The plan's ADRs (harness and metrics, judge, in-house corpus), then the phase file
    again if it is amended.
24. `notebooks/phase-2/01_*` — measuring a RAG: why end-to-end metrics hide
    the real problem. Modules: `eval/` (BEIR, HotpotQA, SQuAD 2.0, QASPER runners; separate
    retrieval and generation metrics; N runs and bootstrap). First check: the harness
    reproduces the nDCG@10 of block 3.
25. `notebooks/phase-2/02_*` — LLM-as-judge: calibrate it or do not use it. Modules:
    `eval/` (judge, calibration, kappa), rubrics in `prompts/`.
26. `notebooks/phase-2/03_*` — contamination: why your good scores may be lying.
    The in-house corpus (2.5), its download script, its license.
27. `notebooks/phase-2/04_*` — building a golden set from nothing, at small scale. The
    review CLI, the versioned golden set in `data/` with its CHANGELOG.
28. The evaluation gate (2.7): `make eval`, `make eval-gate`, the `pre-push` hook, the CI
    job, and the notebook passage that honestly compares it to a blocked merge in a team.
29. Ragas, promptfoo, DeepEval: the comparison in the notebook, after ours.

**What awaits you**: choose the in-house corpus among three candidates (2.5); annotate
50 examples by hand to calibrate the judge (2.3); review in full the 50 to 80 questions
of the golden set via the CLI (2.6).

**At closing**: the closing entry of `JOURNAL.md` (narrative, incidents), the measured
baseline of the phase 1 system against the literature, `STATE.md`.

## Block 7 — Phase 3, advanced RAG and operated pipeline (⏳)

**Before `GO PHASE 3`**: [roadmap/phase-3.md](roadmap/phase-3.md); reread in
[ADR 007](adr/007-sources-ingestion-pgvector.md) the "one index = one table" choice: it is
the starting point of lineage. Block 5 must be done.

**During the phase, in order**:

30. The orchestrator ADR (Dagster vs Airflow vs Prefect) and the ADRs of the techniques
    kept or removed.
31. `notebooks/phase-3/01_*` — why hybrid search saves acronyms and jargon.
    Modules: `retrieval/` (BM25, RRF fusion, cross-encoder re-ranking).
32. `notebooks/phase-3/02_*` — the duel of chunking strategies on raw documents
    (QASPER), and the PDF parsing postponed from phase 1. Modules: `ingest/`.
33. `notebooks/phase-3/03_*` — query transformation: when it helps, when it costs for
    nothing (HyDE, multi-query, decomposition, routing). Modules: `retrieval/`, `generation/`.
34. `notebooks/phase-3/04_*` — our pipeline against LlamaIndex and against Bedrock Knowledge
    Bases on the same BEIR dataset. The two ports live in the benchmark material, not in
    `src/`; the AWS service is created and destroyed within the day.
35. `notebooks/phase-3/05_*` — the experiment matrix: regenerating a hundred indexes without
    recomputing everything. The orchestrated pipeline, Pandera at the input, lineage; the infra
    guide for the orchestrator on the cluster.
36. GraphRAG, last, and its measured removal if it brings nothing.

**What awaits you**: the acceptance criterion — regenerate any row of the master
table from scratch, with a single command. To be tested by you.

**At closing**: table "technique → gain with confidence interval → p95 → EUR",
gap to the literature, "regeneration of a row from scratch" row.

## Block 8 — Phase 4, multi-source agents (⏳)

**Before `GO PHASE 4`**: [roadmap/phase-4.md](roadmap/phase-4.md); reread
[sources/types.py](../src/llm_testbench/sources/types.py): every connector plugs into it.

**During the phase, in order**:

37. The plan's ADRs (in-house orchestration base then LangGraph, routing, AgentCore as an
    option).
38. `notebooks/phase-4/01_*` — an agent without a framework, the bare mechanics, then the same
    agent on LangGraph, smolagents, OpenAI Agents SDK and CrewAI, compared by the numbers.
    Modules: `agents/` (state machine, tool schemas, guardrails); the ports in the
    benchmark material.
39. `notebooks/phase-4/02_*` — text-to-SQL, from the schema to the safe query (Spider, BIRD
    Mini-Dev). Modules: `sources/` (SQL connector, catalog, sqlglot safety pipeline,
    read-only role).
40. `notebooks/phase-4/03_*` — tools, APIs and side effects (OpenAPI, human confirmation,
    propagated identity, tau2-bench).
41. `notebooks/phase-4/04_*` — structured data and images: extracting without hallucinating
    (sandbox, DocVQA, ChartQA, CORD, FUNSD); the time series generator.
42. `notebooks/phase-4/05_*` — multi-source routing and contradictory sources,
    explicit router vs an agent that decides alone, both measured.
43. `notebooks/phase-4/06_*` — evaluating an agent: trajectories, execution, extraction (BFCL,
    tau2-bench, AgentDojo). The phase 2 harness extended, not a second one.
44. `notebooks/phase-4/07_*` — agent memory: what to retain, where, at what cost.
45. The MCP server and the composition of several servers (4.8), A2A under discussion; the
    case where the agent is the wrong answer, measured.

**What awaits you**: you are the human confirmation on side effects (4.3); the
indirect injection attacks are for you to replay yourself (4.7).

**At closing**: SQL execution accuracy, per-field accuracy, routing confusion matrix,
BFCL, tau2-bench and AgentDojo scores.

## Block 9 — Phase 5, LLMOps (⏳)

**Before `GO PHASE 5`**: [roadmap/phase-5.md](roadmap/phase-5.md); reread in
[ADR 009](adr/009-single-environment-oidc-aws-services.md) the AWS services entry
rule; guides [07](infra/07-observability.md) and [09](infra/09-github-oidc-deployment.md)
are the foundation.

**During the phase, in order**:

46. The synthetic traffic generator first: its module, its profiles, and the README
    paragraph that says what it does not capture.
47. The queue ADR (SQS vs Postgres `SKIP LOCKED`, Redis Streams or not) and the
    collector ADR.
48. `notebooks/phase-5/01_*` — anatomy of a trace, and where the milliseconds come from.
    Modules: `obs/`; infra guide ADOT vs vanilla collector.
49. `notebooks/phase-5/02_*` — the cost model, from the token to the price per user. Budgets,
    kill switch, Cost Anomaly Detection guide, Karpenter guide.
50. `notebooks/phase-5/03_*` — detecting a quality regression in production without labels.
    Asynchronous judge, queue and worker, SQS guide, drift detection.
51. The prompt registry, A/B behind a flag, canary and shadow in the chart; the
    JSON dashboards.
52. The three runbooks: provider unavailable · quality degraded without a code change ·
    costs tripled overnight.
53. The minimal chat UI, at the end of the phase.

**What awaits you**: play the three runbooks for real on the cluster, not just read them;
drive the generator's profiles, drift included.

**At closing**: cost per profile extrapolated to the month, detection delays (drift, cost) on
injected drift, Karpenter scale-up time.

## Block 10 — Phase 5B, the bridge (⏳)

**Before `GO PHASE 5B`**: [ADR 005](adr/005-phase-5b-the-bridge.md) then
[roadmap/phase-5b.md](roadmap/phase-5b.md); reread the three locks of `CLAUDE.md` §6.

54. `notebooks/phase-5b/01_*` — choosing between an XGBoost and an LLM, the answer is a
    table. Modules: `classic/` (never exposed by the API), runners in `eval/`, serialization
    template in `prompts/`, the run manifest.
55. `docs/decision-tree-ml-vs-llm.md`, the key deliverable: each branch cites a number.

**At closing**: the table of the 5B.3 axes, the contamination signal next to each
number.

## Block 11 — Phase 6, inference and open models (⏳ · GPU)

**Before `GO PHASE 6`**: [roadmap/phase-6.md](roadmap/phase-6.md); the state of the GPU quota
in `STATE.md`; reread
[llm/providers/openai_compatible.py](../src/llm_testbench/llm/providers/openai_compatible.py)
and the `local` backend of [config/llm_backends.toml](../config/llm_backends.toml): vLLM
plugs in there.

56. The GPU target ADR (ephemeral specialized provider vs node group on the existing EKS)
    and the corresponding infra guide; destruction must be obvious.
57. `notebooks/phase-6/01_*` — what vLLM really does under the hood (continuous batching,
    PagedAttention, KV cache).
58. `notebooks/phase-6/02_*` — the real quality cost of quantization (AWQ, GPTQ, FP8),
    measured by the harness.
59. `notebooks/phase-6/03_*` — self-host vs API, the full calculation (throughput, latency,
    sizing, switch-over threshold); self-hosted embeddings and reranker.
60. LoRA/QLoRA and its run manifest; the cases where fine-tuning was not the right
    answer; phase 5B replayed on a self-hosted model; the "cost of
    governance" row.

**What awaits you**: check every evening that the GPU is destroyed.

**At closing**: cost per million tokens, cold start and scale-up time on each target.

## Block 12 — Phase 7, residual security and compliance (⏳)

**Before `GO PHASE 7`**: [roadmap/phase-7.md](roadmap/phase-7.md); the in-house corpus of
block 6 provides the poisoned documents.

61. The plan's ADR (Bedrock Guardrails as a comparison arm, or not).
62. The notebook or notebooks decided in the plan: the roadmap names none. OWASP LLM Top 10 on
    the full architecture, injection through documents, exfiltration via citations, output
    filtering, Presidio, red teaming (garak, promptfoo) in the CI.
63. `docs/ai-act.md`: risk classification, documentation, logging, GDPR
    minimization, on a hypothetical deployment; the phase 5B defensibility grid
    attaches to it.

**What awaits you**: being able to hold the AI Act conversation in an interview, not producing a
compliance file.

## Block 13 — Phase 8, packaging (⏳ · starts as early as phase 2)

This block is not read in one go: [roadmap/phase-8.md](roadmap/phase-8.md) first, then
as the phases go.

64. At each phase closing, the "Incidents / surprises" section of `JOURNAL.md`: the
    three interview incident stories come out of it, never reconstructed after the fact.
65. The README as the master table grows (from phase 2), with the
    "regeneration from scratch" row (phase 3), the decision tree (5B), the "cost of
    governance" row (phase 6), the limits of the setup.
66. The two posts: the evaluation harness, and self-host vs API with our numbers.
67. Interview preparation: timed system design, build vs buy on three
    building blocks, three situation-action-quantified-result stories. Check the reasoning
    on the word "pipeline" (2026-10-15) against real job offers.

## Block 14 — Phase 9, voice (⏳ · extension)

**Before `GO PHASE 9`**: [roadmap/phase-9.md](roadmap/phase-9.md); the verification of the
datasets (VoiceBench or equivalent), same protocol as phase 0, and its ADR.

68. `notebooks/phase-9/01_*` — where the latency of a voice agent comes from, millisecond by
    millisecond (time-to-first-audio per stage).
69. `notebooks/phase-9/02_*` — evaluating an agent you listen to. The STT → agent → TTS pipeline
    behind the existing API, barge-in, degradation to text.

**At closing**: cost per minute vs cost per text request; GO/NO-GO decision on
phase 10.

## Block 15 — Phase 10, browser and computer use (⏳ · if GO)

[roadmap/phase-10.md](roadmap/phase-10.md), then `notebooks/phase-10/01_*` — an agent that
clicks: the browser tool behind the existing interface, the phase 4 guardrails and
indirect injection multiplied, measured on WebArena or equivalent. If NO-GO, only the
README's "not done, and why" paragraph is to be read.

---

## Maintaining this file

- At each phase closing (`CLAUDE.md` §3 protocol, "Traces" step), the block's ⏳ items
  become real links: notebook slugs, numbered ADRs, infra guides inserted at
  their place of execution, `src/` modules named in the order in which the notebooks
  display them.
- If a phase is amended (`decisions.md`), the corresponding block is corrected in the same
  commit, like the phase file.
- This file carries no status. "Done / not done" and "remaining" are in
  `STATE.md`.
