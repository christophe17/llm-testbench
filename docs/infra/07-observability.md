# Guide 07 — Observability: self-hosted Langfuse, OpenTelemetry traces, cost per span

**Duration**: 30 minutes, 10 of them waiting. **Prerequisites**: guide 01 (local cluster), Docker
VM at 12 GB recommended (8 GB works, tightly). **Cost**: €0 locally. **Code**:
`src/llm_testbench/obs/tracing.py`, `infra/k8s/local/observability/`,
`infra/helm/langfuse/values-local.yaml`, `make langfuse-*` targets.

---

## The problem

An LLM call without a trace is a billed black box: you know neither which exact prompt
went out, nor which model answered, nor how many tokens were read from the cache, nor what
it cost, nor why it was slow. And when quality drops "with no code change"
(phase 5 runbook), the trace is the only proof. So, from the very first call, we need
**one trace per call** with its attributes, sent to a system that can read them,
aggregate them and display them — **on our own infrastructure**, because the traces contain
the prompts, hence the data (governance, ADR 006).

## The options

| Option | Verdict |
|---|---|
| Langfuse SDK in the code (decorators, `langfuse.trace()`) | Simple, but the application code depends on a trace provider. Rejected: we instrument with **OpenTelemetry**, a standard, and Langfuse is only a receiver. |
| Langfuse Cloud | Zero infra, but the prompts go to a third party: contrary to the brief (self-hosted). |
| **Self-hosted Langfuse, fed over OTLP** | **Chosen**: the code has only an OTel exporter; Langfuse, Tempo or Jaeger plug in without modifying it. |
| Grafana Tempo + homemade dashboards | Generic, without the "LLM" reading (prompts, costs, sessions). Prometheus/Grafana arrive in phase 5 for metrics, not to replace Langfuse. |

**For ClickHouse locally** (Langfuse v4 stores events in ClickHouse): the official
2.x chart deploys it through an **operator** (CRD, three keepers, 2 GB of reserved memory) —
too heavy for "the strict minimum" on a Mac. The chart accepts an external, non-clustered
ClickHouse: **a 60-line StatefulSet**, official multi-arch image, does the job.

## Guided reading of the real code

**[`obs/tracing.py`](../../src/llm_testbench/obs/tracing.py)** — two families of attributes
set on every span: `gen_ai.*` (OpenTelemetry **GenAI semantic conventions**:
operation, provider, requested and served model, tokens, finish reason) and `llm_testbench.*`
(what the convention does not cover and the testbench measures: cost, cache, attempts,
governance, prompt hash). `configure_tracing` installs a tracer provider
with either a supplied exporter (in-memory, for tests and notebooks) or an
**OTLP/HTTP** exporter to an endpoint; `langfuse_otlp_headers` builds the Basic auth
header `public key:secret key` that Langfuse expects.

**[`app/main.py`](../../src/llm_testbench/app/main.py)**, `_configure_tracing_from`: the API
reads `LLM_TESTBENCH_OTLP_ENDPOINT` and the two keys from its settings; with no endpoint, the
spans are no-ops — the application code does not change by a single line.

**[`infra/k8s/local/observability/clickhouse.yaml`](../../infra/k8s/local/observability/clickhouse.yaml)**
— a single-node StatefulSet, plaintext password (local only), `/ping` probe,
10 GB `local-path` volume.

**[`infra/helm/langfuse/values-local.yaml`](../../infra/helm/langfuse/values-local.yaml)** —
the points to read:

- `clickhouse.deploy: false`, `crdCheck: false`, `host`, `cluster.enabled: false`,
  `migration.url`: the chart uses our ClickHouse and does not look for the operator;
- `postgresql`, `redis` (Valkey), `s3` (SeaweedFS) embedded, reduced volumes — Langfuse v4
  needs all four: Postgres for metadata, ClickHouse for events,
  Redis for queues, S3 for raw payloads;
- `langfuse.additionalEnv` with `LANGFUSE_INIT_*`: **headless initialization** —
  organization, project, user and **API keys** created at first startup, so that
  the testbench API can trace without a human clicking in the UI. The values are
  dev constants; in the cloud (phase 5), they will come from Secrets Manager.

## Run

**1. Deploy** (~1.5 GB of images the first time, ~10 minutes):

```bash
make langfuse-up
kubectl -n observability get pods
```

Expected: `clickhouse-0`, `langfuse-postgresql-0`, `langfuse-redis-*`, `langfuse-s3-*`,
`langfuse-web-*`, `langfuse-worker-*` in `Running`. The `web` pod restarts two or three
times during the ClickHouse migrations (46 migrations): normal. **If the `worker` started
before the migrations finished, restart it** (`kubectl -n observability rollout restart
deploy/langfuse-worker`): otherwise it would get "table does not exist" errors and would
not consume the queues.

**2. Open the UI**:

```bash
make langfuse-port-forward &
open http://localhost:3000     # dev@llm-testbench.local / local-only-password
```

Project `phase-1` already created (headless initialization).

**3. Send a trace from the LLM layer, with no key and no network** — the simulated provider
is enough, the trace is real:

```bash
uv run python - <<'PY'
import asyncio
from llm_testbench.llm import CompletionRequest, DataClass, Message, ModelRef, Role
from llm_testbench.llm.client import LLMClient
from llm_testbench.llm.testing import Step, anthropic_message, scripted_anthropic_provider
from llm_testbench.obs.tracing import configure_tracing, get_tracer, langfuse_otlp_headers
tp = configure_tracing(otlp_endpoint="http://localhost:3000/api/public/otel/v1/traces",
                       otlp_headers=langfuse_otlp_headers("pk-lf-local-0000000000000000", "sk-lf-local-0000000000000000"),
                       set_global=False)
client = LLMClient.from_settings(tracer=get_tracer(tp))
client.register_provider("anthropic", scripted_anthropic_provider([Step(json_body=anthropic_message("Paris.", input_tokens=900, output_tokens=7))])[0])
req = CompletionRequest(model=ModelRef.parse("anthropic/claude-sonnet-5"),
                        messages=(Message(role=Role.USER, content="Capital of France?"),), data_class=DataClass.PUBLIC)
print(asyncio.run(client.complete(req)).cost_usd); tp.force_flush(); tp.shutdown()
PY
```

**4. Read it back through the v2 API** (Langfuse v4 runs in `events_only` mode: the old
`/api/public/traces` and `/observations` endpoints return 404, this is documented):

```bash
curl -s -u pk-lf-local-0000000000000000:sk-lf-local-0000000000000000 \
  "http://localhost:3000/api/public/v2/observations?limit=1" | python3 -m json.tool | head -40
```

Expected: a `GENERATION` observation named `chat anthropic/claude-sonnet-5`, `model`
`claude-sonnet-5`, `usage` 900/7, and a **cost computed by Langfuse** (`calculatedTotalCost`)
equal to the one from our pricing table ($0.00187 for 900 + 7 tokens on Sonnet 5). Two
independent pricing tables that agree: a free cross-check.

**5. Connect the cluster's API**: `values-local.yaml` already carries the in-cluster endpoint
(`http://langfuse-web.observability:3000/...`) and the local keys. Redeploy the API
(guide 01, step 4 or `tilt up`): every `/chat` produces a trace.

**6. Read a trace in the UI**: Tracing → Observations. Open one: the
`gen_ai.*` and `llm_testbench.*` attributes are in the metadata, the model and usage
in the header, the computed cost on the right.

## Pitfalls

- **Langfuse v4 = `events_only`**: guides and SDKs from before 2026 talk about
  `/api/public/traces`; those calls return 404. Reads go through
  `/api/public/v2/observations` (bound them with `fromStartTime`/`toStartTime`) and Metrics v2.
- **Startup order**: a worker that starts during the migrations stays in error
  without restarting. The symptom: the payloads are indeed in the S3 bucket
  (`otel/<project>/...json`), nothing arrives in ClickHouse. A `rollout restart` is enough.
- **Langfuse cost at 0 on the very first observation**: its pricing table is loaded
  into cache on the first pass; the second observation is priced. Our cost, on the other hand,
  is computed client-side: it is the one we use for the tables.
- **OTLP returns 200 even on an empty body**: a 200 does not prove ingestion;
  only the read-back (step 4) proves it.
- **Memory**: ClickHouse + SeaweedFS + Postgres + Valkey + web + worker ≈ 2.5 GB reserved.
  With an 8 GB VM plus our Postgres and the API, it fits; with a local model (phase 6), it does not.
- **`$path` in zsh is `PATH`**: a `for path in …` loop in a verification script
  wiped the shell's PATH during the diagnosis. Twenty minutes lost to a variable
  name — recorded so that it only happens once.

## Interview questions

<details><summary><b>1. Why instrument with OpenTelemetry rather than with the Langfuse SDK?</b></summary>

So that the application code depends on no trace provider: an OTLP exporter can be pointed
at Langfuse, Tempo, Jaeger or a collector without changing a line. The GenAI semantic
conventions provide a vocabulary they can all read. The price: a few specific
attributes (sessions, scores) are less direct than with the native SDK.
</details>

<details><summary><b>2. What does a useful LLM call trace contain, and why these fields?</b></summary>

The requested model *and* the served model (a provider can change revision), the input
and output tokens, the tokens read from and written to the cache (the cost depends on them),
the finish reason (a truncated answer is not an answer), the cost, the number of attempts,
the governance decision, the prompt hash (to tie a number to the exact text that produced it).
</details>

<details><summary><b>3. Why does Langfuse need four stores?</b></summary>

Postgres for transactional metadata (projects, users, keys), ClickHouse
for analytical events (voluminous, queried through aggregates), Redis for the asynchronous
ingestion queues, S3 for raw payloads (prompts, responses) you do not want
in a database. It is the architecture of an event analytics system, not
of a CRUD application.
</details>

<details><summary><b>4. Traces contain the prompts: what are the consequences?</b></summary>

So they contain user data: the same governance policy as the
calls themselves (self-hosted, retention, access), PII masking before export (phase 7),
and access control on the UI. A trace sent to a tracing SaaS is data
that leaves.
</details>

## What we did not do, and why

- **No OTel collector or Prometheus/Grafana**: phase 5, when there are
  load metrics to aggregate (traffic generator); in phase 1, Langfuse is enough.
- **No Langfuse in the cloud**: it will follow the API onto EKS in phase 5 with the same chart
  (ClickHouse via the operator this time, on properly sized nodes).
- **No scores or sessions**: they arrive with the judge (phase 2) and agent
  memory (phase 4).
- **No prompt masking in traces**: public data in phase 1; Presidio
  in phase 7.
