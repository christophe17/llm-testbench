# Guide 01 — Local dev: k3d, Postgres/pgvector, the API in the cluster, the Tilt loop

**Duration**: 20 minutes the first time. **Prerequisites**: Docker Desktop (VM with 12 GB of
memory recommended to accommodate Langfuse in guide 07), k3d ≥ 5.9, kubectl, Helm ≥ 3,
Tilt. **Cost**: €0. **Code**: `infra/k3d/`, `infra/k8s/local/`, `Tiltfile`, `Dockerfile`.

---

## The problem

The API must run **as in production** from phase 1 on: in a container, on Kubernetes,
behind probes, with its secrets injected and a Postgres database next to it. But iteration
must stay fast: save a file and see the effect in two seconds, not in a two-minute build.
And everything must run on an Apple Silicon Mac without emulation, which makes Docker ten
times slower.

## The options

| Option | Verdict |
|---|---|
| Docker Desktop's Kubernetes | Rejected by the brief: a single fixed cluster, no local registry, opaque configuration. |
| minikube / kind | Decent. kind is close to k3d; minikube is heavier (VM). |
| **k3d** (k3s in Docker) | **Chosen**: starts in 30 s, built-in local registry, declarative configuration, multiple clusters possible. |
| No local Kubernetes, `uvicorn` alone | Useful for a quick test (`make api`), but we would never see the probes, the secrets and the chart before the cloud. |

For the dev loop: **Tilt** rather than Skaffold, for its `live_update` (syncs files into
the container without rebuilding the image) and its dashboard.

## Guided reading of the real code

**[`infra/k3d/config.yaml`](../../infra/k3d/config.yaml)** — a single server node (no
agent: a Mac does not need to simulate three machines), a **local registry**
`llm-testbench-registry` exposed on host port 5050, Traefik disabled (we expose through
port-forward, no Ingress locally). The registry is the subtle point: from your Mac it is
called `localhost:5050`, from inside the cluster `llm-testbench-registry:5050` — k3d adds
the DNS entry in the nodes.

**[`infra/k8s/local/`](../../infra/k8s/local/)** — a kustomize with the namespace, a
Postgres `StatefulSet` on the `pgvector/pgvector:pg16` image (native arm64 build, verified:
no emulation) with a `local-path` volume (k3s's default provisioner), `pg_isready` probes,
and a `pgvector-init` `Job` that runs `CREATE EXTENSION vector`. The password is in plain
text in a `Secret`: **locally only**; in the cloud it is External Secrets (guide 05).

**[`Dockerfile`](../../Dockerfile)** — two stages. The first resolves dependencies with
`uv` in two layers: `pyproject.toml` + `uv.lock` first (Docker cache: almost never
changes), the code next. The second starts again from a minimal Python image, without `uv`
or a compiler, copies the venv, and runs as a non-root user (`uid 10001`). The base images
exist in arm64 and amd64: the same recipe produces the Mac image and the cloud one.

**[`Tiltfile`](../../Tiltfile)** — four resources: Postgres and its job (kustomize), a
`local_resource` that creates the API keys `Secret` from `.env`, the image build with
`live_update` (syncing `src/`, `prompts/`, `config/` into the container; `uvicorn --reload`
is not enabled in the image, so a code change requires a pod restart by Tilt, which it does
on its own), and the API Helm chart with its local values (guide 06).

**[`Makefile`](../../Makefile)** — `k3d-up`, `k3d-down`, `pg-port-forward`,
`k8s-secrets`, `docker-build`, `helm-lint`, `tilt-up`, `ingest-scifact`, `api`.

## Run

**1. The cluster and the database.**

```bash
make k3d-up
kubectl config current-context        # must print k3d-llm-testbench
kubectl -n llm-testbench get pods     # postgres-0 Running, pgvector-init Completed
```

The 2026-08-26 journal entry tells of a `kubectl apply` that went to an old cluster: **check the
context** before any `apply`, it is the cheapest reflex there is.

**2. Check pgvector from your machine.**

```bash
make pg-port-forward &      # leaves a port-forward in the background
LLM_TESTBENCH_DATABASE_URL=postgresql://testbench:testbench-local-only@localhost:5432/testbench \
  uv run python -c "import psycopg; c=psycopg.connect('$LLM_TESTBENCH_DATABASE_URL'); \
  print(c.execute(\"select extversion from pg_extension where extname='vector'\").fetchone())"
make test-db                 # the 6 storage tests against the real database
```

Expected: `('0.8.6',)` then `6 passed`.

**3. The secrets.** Copy `.env.example` to `.env`, fill in your keys, then:

```bash
make k8s-secrets
kubectl -n llm-testbench get secret llm-testbench-api-secrets -o jsonpath='{.data}' | head -c 200
```

The `Secret` contains every line of `.env` (API keys and database URL). It is neither in
the chart nor in git.

**4. The image and its deployment, by hand once** (to see each step):

```bash
make docker-build
docker tag llm-testbench-api:dev localhost:5050/llm-testbench-api:dev
docker push localhost:5050/llm-testbench-api:dev
helm upgrade --install api infra/helm/llm-testbench-api -n llm-testbench \
  -f infra/helm/llm-testbench-api/values-local.yaml --set image.tag=dev
kubectl -n llm-testbench get pods -w
```

The pod goes `Running` but stays `0/1 READY` with `Readiness probe failed: 503`. **This is
intended**: `/readyz` refuses traffic as long as the configured index does not exist in the
database. A pod that cannot answer must not receive requests, and it says why:

```bash
kubectl -n llm-testbench port-forward svc/api 8000:80 &
curl -s localhost:8000/readyz
```

Expected: `{"error":"not_ready","detail":"index 'scifact-recursive-oai-small' missing from the registry: run the ingestion",...}`.

**5. The ingestion** (OpenAI key required for the embeddings, ~5,000 abstracts, ~$0.05):

```bash
set -a; source .env; set +a
make ingest-scifact
curl -s localhost:8000/readyz            # {"status":"ready"}
curl -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"question": "Does vitamin D deficiency increase mortality?", "k": 5}' | python3 -m json.tool
```

You should see an answer with `[n]` citations, the evidence and its provenance, the cost and
the trace ID.

**6. The dev loop.**

```bash
make tilt-up
```

Tilt opens a dashboard (`http://localhost:10350`): it builds the image, pushes it to the
local registry, deploys the chart, exposes `8000`. Edit a file in `src/`: Tilt syncs it into
the container and restarts the pod. `Ctrl-C` then `tilt down` to remove the API (Postgres
stays).

## Pitfalls

- **The wrong kubectl context.** `k3d cluster create` changes the current context, a
  leftover cluster may be lying around. `kubectl config current-context`, always.
- **The port-forward drops** as soon as the pod restarts (Tilt restarts it, a
  `kubectl port-forward` launched by hand does not). If `curl` fails for no reason, restart
  it.
- **Helm's `--wait` and readiness.** `helm upgrade --wait` waits for the pods to be
  `Ready`; without an index, it will time out. This is not a chart bug, it is readiness
  doing its job. Ingest first, or deploy without `--wait`.
- **Docker VM memory.** Postgres + API fit in 8 GB; Langfuse (guide 07) adds ClickHouse,
  Redis and MinIO: raise the VM to 12 GB in Docker Desktop.
- **Images without an arm64 build.** An amd64-only image runs under emulation, ten times
  slower, and sometimes not at all. `docker manifest inspect <image> | grep arm64` before
  adopting an image.
- **The local registry is not `localhost` inside the cluster.** A pod pulls
  `llm-testbench-registry:5050/...`; you push to `localhost:5050/...`. The chart's local
  values use the first name.
- **`.env` loaded twice.** The Kubernetes `Secret` is created from `.env`; the local
  `make api` also reads `.env` (pydantic-settings). After changing a key, rerun
  `make k8s-secrets` *and* restart the pod: an updated `Secret` is not reread by a running
  process.

## Interview questions

<details><summary><b>1. Difference between liveness, readiness and startup probes?</b></summary>

Liveness: "is the process alive?" — on failure, the container is restarted. Readiness: "can
it serve traffic right now?" — on failure, the pod is removed from the Service, without a
restart. Startup: "has it finished starting?" — disables the other two during startup, so as
not to kill a process that is slow to initialize. The API uses `/healthz` for liveness and
startup, `/readyz` (database + index) for readiness.
</details>

<details><summary><b>2. Why not put the API key in the image or in the chart?</b></summary>

An image gets shared and scanned, a chart gets versioned: both leak. The secret lives in a
Kubernetes `Secret` created outside the chart (locally from `.env`, in the cloud from
Secrets Manager via External Secrets), and the chart only references it.
</details>

<details><summary><b>3. What is a local registry with k3d for?</b></summary>

So that the nodes pull the image we just built without going through a remote registry: no
push over the Internet, no credentials, two seconds instead of a minute. The price: two
names for the same registry (host and cluster), which you need to know.
</details>

<details><summary><b>4. What exactly does Tilt sync, and when does it rebuild the image?</b></summary>

`live_update` copies the modified files (here `src/`, `prompts/`, `config/`) into the
running container. Any change outside these paths (Dockerfile, `pyproject.toml`,
`uv.lock`) triggers a full rebuild.
</details>

## What we did not do, and why

- **No local Ingress**: port-forward is enough for a single developer; Ingress is a cloud
  question (guide 03).
- **No `uvicorn --reload` in the image**: the image is the production one; reloading is
  Tilt's job (pod restart), not the image's.
- **No Langfuse here**: guide 07, once the API is in place.
- **No automated integration tests against the cluster**: CI stays offline (ADR 003); the
  local cluster is checked by hand, with this guide.
