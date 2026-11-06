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

**[`Tiltfile`](../../Tiltfile)** — the only owner of what runs in the cluster: nothing applies
`infra/k8s/local/` besides it. Four resources: Postgres and its job (kustomize), a
`local_resource` that creates the API keys `Secret` from `.env`, the image build with
`live_update` (syncing `src/`, `prompts/`, `config/` into the container, where
`uvicorn --reload`, set by the local chart values only, restarts the server process: guide
01b, step 8), and the API Helm chart with its local values (guide 06). The subtle point is
`objects=`: Tilt files every object without a pod (namespace, `Secret`, `ConfigMap`) under an
`uncategorized` resource. The Tiltfile attaches the namespace and the database `Secret` to
`postgres`, and the API's `ServiceAccount` and `ConfigMap` to `api`, so that
`tilt up postgres pgvector-init` deploys everything Postgres needs, and that nothing is
applied to the namespace before it exists.

**[`Makefile`](../../Makefile)** — `k3d-create` (create the cluster, once), `k3d-up`
(start it again when it is stopped), `k3d-down` (destroy it), `pg-port-forward`, `psql`,
`db-ui`, `k8s-secrets`, `docker-build`, `helm-lint`, `tilt-up`, `ingest-scifact`, `api`.

## Run

**1. The cluster and the database.**

```bash
make k3d-create                       # once; afterwards, make k3d-up
kubectl config current-context        # must print k3d-llm-testbench
make tilt-db                          # in a second terminal: Postgres and its job only
kubectl -n llm-testbench get pods     # postgres-0 Running, pgvector-init Completed
```

The 2026-08-26 journal entry tells of a `kubectl apply` that went to an old cluster: **check the
context** before Tilt deploys anything, it is the cheapest reflex there is.

`make tilt-db` runs `tilt up postgres pgvector-init`: Tilt starts only the resources named,
without building the API image, and forwards Postgres to `localhost:5432` for as long as it
runs. `Ctrl-C` stops Tilt and the port-forward; the pods keep running
(`make pg-port-forward` then gives you access back without Tilt).

**2. Check pgvector from your machine.**

```bash
LLM_TESTBENCH_DATABASE_URL=postgresql://testbench:testbench-local-only@localhost:5432/testbench \
  uv run python -c "import psycopg; c=psycopg.connect('$LLM_TESTBENCH_DATABASE_URL'); \
  print(c.execute(\"select extversion from pg_extension where extname='vector'\").fetchone())"
make test-db                 # the 6 storage tests against the real database
```

Expected: `('0.8.6',)` then `6 passed`.

**2b. Look inside the database.** Two doors onto the same port-forward, both built on the
`DATABASE_URL` of the Makefile:

```bash
make psql                    # the psql REPL: \dt, \d <table>, EXPLAIN ANALYZE
make db-ui                   # Harlequin: catalog tree, editor with completion, results grid
```

Harlequin is a SQL IDE in the terminal (a TUI): the middle ground between a desktop client,
whose connections live outside the repo, and a web UI, which would need a deployment. It is a
dev dependency of the project, so `make setup` installs it, and it reads its connection from
[`.harlequin.toml`](../../.harlequin.toml) at the repo root: one `local` profile whose DSN is
the dev constant of the Makefile, overridden by `LLM_TESTBENCH_DATABASE_URL` when that variable
is set. This is why `make db-ui DATABASE_URL=...` reaches another database (RDS, later) with
no second profile and no password in a versioned file. Keys: `F6` the catalog, `F2` the editor,
`Ctrl-Enter` runs the query, `Ctrl-E` exports the result, `F1` the full list, `Ctrl-Q` quits.
The profile's `limit = 1000` is applied by Harlequin, not by Postgres: a `SELECT *` on a vector
table of phase 1 returns every embedding as text, and the guard keeps the grid usable. Columns
of type `vector` display as plain text, nothing more. `uv run hsql -P local -c "select 1"` runs
a query through the same profile without the UI, handy from a script.

**3. The secrets.** Copy `.env.example` to `.env`, fill in your keys, then:

```bash
make k8s-secrets
kubectl -n llm-testbench get secret llm-testbench-api-secrets -o jsonpath='{.data}' | head -c 200
```

The `Secret` contains the credential lines of `.env` only (the provider keys), neither in
the chart nor in git. The `LLM_TESTBENCH_*` lines stay out on purpose: they are the laptop's
settings (database and Langfuse on `localhost`), and the pod gets its own from the chart's
`ConfigMap` (`values-local.yaml`). The deployment lists the `Secret` after the `ConfigMap`,
so a `Secret` built from the whole file would override the in-cluster database URL with
`localhost:5432`, which inside a pod is nothing: the API would crash at start-up on
"connection refused".

**4. The image and its deployment, by hand once** (to see each step):

```bash
make docker-build
docker tag llm-testbench-api:dev localhost:5050/llm-testbench-api:dev
docker push localhost:5050/llm-testbench-api:dev
helm upgrade --install api infra/helm/llm-testbench-api -n llm-testbench \
  -f infra/helm/llm-testbench-api/values-local.yaml
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

**5. The ingestion** (OpenAI key in `.env` for the embeddings, ~5,000 abstracts, ~$0.05):

```bash
make ingest-scifact
curl -s localhost:8000/readyz            # {"status":"ready"}
curl -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"question": "Does vitamin D deficiency increase mortality?", "k": 5}' | python3 -m json.tool
```

You should see an answer with `[n]` citations, the evidence and its provenance, the cost and
the trace ID.

**6. The dev loop.**

```bash
make tilt-up                 # stop make tilt-db first: one Tilt at a time
```

Tilt opens a dashboard (`http://localhost:10350`): it builds the image, pushes it to the
local registry, deploys the chart, exposes `8000`. Edit a file in `src/`: Tilt syncs it into
the container and restarts the pod. `Ctrl-C` stops Tilt; the pods keep running. `tilt down`
deletes everything the Tiltfile deploys, **Postgres included**: only the namespace (Tilt
never deletes namespaces by default) and the PVC remain, so the data comes back with the
next `make tilt-db`.

## Pitfalls

- **The wrong kubectl context.** `k3d cluster create` changes the current context, a
  leftover cluster may be lying around. `kubectl config current-context`, always.
- **A stopped cluster after a Docker restart.** The k3d nodes are containers: when Docker
  Desktop restarts, they stay `Exited` and `k3d cluster list` shows `0/1` servers. The
  cluster still exists, so `make k3d-create` fails, and `kubectl` gets `connection refused`
  on the API server port. `make k3d-up` starts it again (`k3d cluster start`), and the pods
  come back on their own; the Postgres volume lives in the node container and survives a
  stop, but not a `k3d-down`.
- **Two owners for the same manifests.** A `kubectl apply -k infra/k8s/local` while Tilt
  manages these objects removes the labels Tilt sets on them: the `StatefulSet`'s pod
  template changes, and Postgres restarts. Tilt is the only owner; the Makefile has no
  `apply` of these manifests.
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
  processes (`make api`, `make ingest-scifact`, the notebooks) export `.env` into their own
  environment at start-up (`load_env_file` in `config.py`). After changing a key, rerun
  `make k8s-secrets` *and* restart the pod: an updated `Secret` is not reread by a running
  process, and neither is `.env` by a running local one.
- **A key in `.env` is not a pydantic setting.** `Settings` owns the `LLM_TESTBENCH_*`
  variables only; `OPENAI_API_KEY` and friends are read from the environment by the backend
  registry at call time, never stored (ADR 006). That is why the entry points export `.env`
  first. Before that call existed, `make ingest-scifact` found the database URL and then
  failed on the key: half of the same file was being read.

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
running container. It restarts nothing: `uvicorn --reload`, set by the local values,
restarts the server process. Any change outside these paths (Dockerfile, `pyproject.toml`,
`uv.lock`) triggers a full rebuild.
</details>

## What we did not do, and why

- **No local Ingress**: port-forward is enough for a single developer; Ingress is a cloud
  question (guide 03).
- **No `uvicorn --reload` in the image**: the image is the production one. The reload is
  set by the local chart values (`args`), which also make the root filesystem writable for
  the sync; the cloud values keep neither (guide 01b, step 8).
- **No Langfuse here**: guide 07, once the API is in place.
- **No automated integration tests against the cluster**: CI stays offline (ADR 003); the
  local cluster is checked by hand, with this guide.
