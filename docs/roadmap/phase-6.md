# PHASE 6 — Inference and open models (weeks 14–15)

**Strategic note**: Switzerland (banking, pharma, insurance) is a constraint of the program,
and data residency and on-premise deployment are strong requirements there. This phase has
above-average value — do not sacrifice it if behind schedule. Propose at least one
European open model in addition to the classic ones.

**vLLM**: continuous batching, PagedAttention, KV cache — I want to understand **why** it is
fast, not only how to launch it. Plugged in as an OpenAI-compatible backend of the LLM
layer (ADR 006).

**Quantization** AWQ / GPTQ / FP8 with **quality impact measured by our harness on the public
datasets**: almost nobody does this measurement, it is exactly what will set me apart.

**Economic model**: throughput vs latency, GPU sizing, cost per million tokens self-host
vs API, **volume break-even threshold**.

**Deployment** of GPUs on Kubernetes, autoscaling, cold start. Self-hosted embeddings and
reranker. Two targets for the same vLLM chart, measured against each other (ADR 009):
(a) an **ephemeral** GPU Terraform module targeting a specialized provider decoupled from the
main cloud — the default path, obvious teardown; (b) **a GPU node group on the existing EKS**
(g6, L4 GPU, Spot via Karpenter), if the "Running On-Demand G and VT
instances" quota has been granted — requested from phase 1 on (`STATE.md`), because it takes
days to weeks. One more row in the table: cost per million tokens, cold start, scale-up
time, on each target. It is the only place where "GPU infra", the program's preferred
engagement (PD-18), and "LLMOps on AWS" meet: the ADR on decoupling becomes an
ADR on the choice of target, quantified.

**Measured governance**: "cost of governance" row of the master table (ADR 006) — what
refusing to route a data class to a non-compliant backend costs.

**Fine-tuning**: a LoRA/QLoRA on a justified case, evaluated against the prompt-only baseline
— **and document the cases where fine-tuning was not the right answer, with numbers to back
it**. Each training run, LoRA included, writes the **run manifest** defined in 5B.3. Keep it
complete enough (hashed config, seed, dataset revision, exact model identifier, metrics, cost)
to serve as an SFT starting point for module R1.1 of the Research Engineer roadmap
(`~/Roadmaps/roadmap-research-engineer`), which assumes phases 2, 3, 6 and 7 are delivered.

**5B replayed**: the LLM arm of phase 5B on a self-hosted model — marginal cost and quality,
one more row in its table.

**Notebooks**: (1) what vLLM really does under the hood; (2) the real quality cost of
quantization; (3) self-host vs API, the full calculation with my numbers.
