# PHASE 5 — LLMOps: observability, cost, operations (weeks 12–13) ⭐ MY WEAPON

This is where my years of DevOps become an advantage. Few AI Engineers can do this phase —
to be polished as carefully as phase 2.

**Prerequisite: the synthetic traffic generator.** There are no users. First a
generator that replays the queries of the public datasets according to configurable profiles —
rate, bursts, mix of question types, share of out-of-scope queries, and **the ability to
make the distribution drift over time**. Everything else in the phase is measured on it. Write
explicitly in the README what this simulation does not capture.

**Traceability** OTel/GenAI + Langfuse: full trace request → routing → retrieval →
reranking → tools → generation, with duration, tokens and cost per span. Collector: **ADOT**
(the AWS distribution of OpenTelemetry) on EKS, the vanilla OTel collector locally — same
OTLP pipeline, two distributions, the difference explained and quantified (what ADOT really
adds).

**Cost and latency.** Cost per request and **per traffic profile**, extrapolated to a monthly
cost for target volumes that you will propose. TTFT and p50/p95/p99 broken down by step under
load. Budgets, alerts, kill switch on cost drift; **Cost Anomaly Detection** (AWS) as a
complement to the homemade kill switch, both detection delays measured on the same injected
drift. **Karpenter** to absorb the traffic generator: on-demand nodes, Spot for the
generator and the evaluation jobs, scale-up time and cost quantified.

**Prompts.** Prompt version registry with hot rollback without redeployment. A/B
testing of prompts behind a feature flag, with statistical analysis on simulated traffic.
Canary and shadow deployment for a prompt or model change.

**Continuous quality.** Sampling of requests to an asynchronous judge, drift detection
on the incoming distribution — measured by injecting a controlled drift from the generator,
which gives a real number: after how many requests does the detection trigger?
Feedback loop: the endpoint and the storage, fed by the judge in the absence of users —
and we say so.

**Queue and worker.** Sampling to the judge and the feedback loop go through a
real queue and a worker, never through an inline call within the request: at-least-once
delivery, idempotency by key, retries, monitored dead-letter queue. An abstraction with two
implementations, like the LLM layer (ADR 006): Postgres `SKIP LOCKED` locally on k3d,
**SQS** on AWS (standard queue, managed dead-letter queue, visibility, native at-least-once);
the phase plan ADR decides the rest (Redis Streams, or not), under the constraint that the
application code never sees the difference (`CLAUDE.md` §4, AWS services entry rule).

**Mandatory runbooks**: the provider is unavailable · quality has degraded without any
code change (the provider silently updated its model) · costs tripled
overnight.

**Minimal chat UI**, at the end of the phase: a page that consumes the SSE streaming, displays
the citations and feeds the feedback endpoint — three things already built at that point. Its
purpose is to make the testbench demonstrable in 30 seconds in an interview or in front of a
client, not to build a product: no heavy front-end framework, no design system, one page.

**Notebooks**: (1) anatomy of a trace and where the milliseconds come from; (2) the
cost model, from the token to the price per user; (3) detecting a quality regression in
production without labels.
