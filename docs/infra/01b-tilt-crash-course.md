# Guide 01b — Tilt crash course: from `tilt up` to a running pod

**Duration**: 30 minutes of reading, 15 of commands. **Prerequisites**: guide 01 step 1 (the
k3d cluster exists). **Cost**: €0. **Code**: `Tiltfile`, `infra/k8s/local/`,
`infra/helm/llm-testbench-api/`, the `tilt-*` and `k8s-secrets` targets of the `Makefile`.

Every output below is real: Tilt v0.37.7 on the k3d cluster, captured on 2026-10-26, trimmed.
The experiments that test Tilt itself rather than this repo's Tiltfile ran in a scratch
directory, on a second Tilt (`--port 10351`) and a throwaway namespace; the "Run" section gives
them so you can replay them.

---

## The problem

Guide 01 uses Tilt as a black box: `make tilt-db`, `make tilt-up`, a dashboard. The Tiltfile
is fifty lines and reads like a Python script, which is the trap: it is not a script that runs
against the cluster from top to bottom. Read it as one and you end up with wrong beliefs, each
with a real cost:

- "`k8s_resource(...)` deploys something": it deploys nothing.
- "A disabled resource is not in the cluster": it may well be, left by an earlier session or
  another tool.
- "Tilt synced my file, so the API runs my code": a sync restarts nothing; here it works only
  because the local values run `uvicorn --reload` (pitfall 1).
- "Disabling a resource is harmless": disabling `postgres` deletes the namespace, and the
  database volume with it (pitfall 2).

This guide follows one `tilt up` from the first line of the Tiltfile to the running pod, then
what Tilt does while it runs, and what it does when it stops.

## The options

Three ways to run a dev loop against a cluster:

| Option | How it works | Verdict |
|---|---|---|
| By hand | `docker build` + `push` + `helm upgrade --install` + `kubectl port-forward` | Every step visible, which is why guide 01 step 4 does it once. A minute or two per change. |
| Skaffold | A pipeline (build → tag → deploy) rerun on every change | Workable; no persistent model of the resources, a thinner file-sync story. |
| **Tilt** | A local controller that reconciles a desired state, the way Kubernetes does | **Chosen** (guide 01): `live_update`, dependencies between resources, a dashboard. The price is a model to learn: this guide. |

## The mental model

Tilt is **a small Kubernetes on your Mac**. `tilt up` starts an API server on
`localhost:10350`, with its own object types and controllers that reconcile them, the same
machinery as kube-apiserver and kube-controller-manager:

```bash
tilt api-resources
```
```
NAME                  APIVERSION          KIND
cmds                  tilt.dev/v1alpha1   Cmd
dockerimages          tilt.dev/v1alpha1   DockerImage
filewatches           tilt.dev/v1alpha1   FileWatch
imagemaps             tilt.dev/v1alpha1   ImageMap
kubernetesapplys      tilt.dev/v1alpha1   KubernetesApply
liveupdates           tilt.dev/v1alpha1   LiveUpdate
portforwards          tilt.dev/v1alpha1   PortForward
tiltfiles             tilt.dev/v1alpha1   Tiltfile
uiresources           tilt.dev/v1alpha1   UIResource
...
```

You query it with `tilt get` the way you query a cluster with `kubectl get`:

| Kubernetes | Tilt |
|---|---|
| the manifests | the Tiltfile |
| `kubectl get pods` | `tilt get uiresources` |
| a controller reconciling a `Deployment` | controllers reconciling a `KubernetesApply`, a `FileWatch`, a `LiveUpdate` |
| `kubectl logs` | `tilt logs <resource>` |
| `kubectl wait` | `tilt wait` |

The Tiltfile is written in **Starlark**, a Python dialect made for configuration. It runs
**once, at load**, and again each time one of its inputs changes. It only *declares*; the
controllers act afterwards, resource by resource. Everything below follows from that split.

## Step 1 — Load: the Tiltfile runs, the cluster is untouched

Each call of the [`Tiltfile`](../../Tiltfile), in file order, and what it really does at load:

| Lines | Call | What happens at load |
|---|---|---|
| [7](../../Tiltfile#L7) | `k8s_yaml(kustomize('infra/k8s/local'))` | runs `kustomize build` **now**, on your Mac, and registers the 5 rendered objects. Nothing is applied. |
| [10-15](../../Tiltfile#L10-L15) | `k8s_resource('postgres', ...)` | configures a resource Tilt will assemble from the registered objects (step 2). Creates nothing. |
| [16](../../Tiltfile#L16) | `k8s_resource('pgvector-init', ...)` | same. |
| [20-26](../../Tiltfile#L20-L26) | `local_resource('api-secrets', ...)` | registers a command to run on your Mac, later. Does not run it. |
| [28-37](../../Tiltfile#L28-L37) | `docker_build(...)` | registers a recipe: "for any object that references `llm-testbench-registry:5050/llm-testbench-api`, build this image from `.` and sync these paths". Builds nothing. |
| [39-45](../../Tiltfile#L39-L45) | `k8s_yaml(helm(...))` | runs **`helm template`** now and registers the rendered objects. Not `helm install`: there is no Helm release, and `helm list` never shows what Tilt deploys. |
| [46-52](../../Tiltfile#L46-L52) | `k8s_resource('api', ...)` | configures the `api` resource. |

Since the whole file runs at every load, `make tilt-db`, which deploys nothing of the API,
still needs `helm` installed and a chart that renders: a broken chart breaks the Postgres loop
too.

`k8s_resource` is a lookup, not a creation. A misspelled name is caught at load, with the exit
code 5 of a Tiltfile error:

```
Tiltfile:2:13: k8s_resource specified unknown resource "postgress". known k8s resources: postgres, pgvector-init
```

You can run the load alone, without deploying anything:

```bash
tilt alpha tiltfile-result | jq -r '.Manifests[] | "\(.Name)  deps=\(.ResourceDependencies // [] | join(","))"'
```
```
postgres  deps=
pgvector-init  deps=postgres
api  deps=postgres,api-secrets
api-secrets  deps=postgres
```

## Step 2 — Assembly: objects become resources

A **resource** is Tilt's unit of work: one row in the UI, one set of objects applied together,
one status. Tilt builds the resources from the registered objects with three rules:

1. Each **workload**, an object that creates pods (`Deployment`, `StatefulSet`, `Job`,
   `DaemonSet`…), becomes a resource named after it: StatefulSet `postgres` → resource
   `postgres`.
2. A **Service** joins the workload whose pod labels its selector matches. An **image** built by
   `docker_build` joins the workloads that use it.
3. **Everything else** (`Namespace`, `Secret`, `ConfigMap`, `ServiceAccount`…) has nothing
   linking it to a workload and goes into a single catch-all resource, **`uncategorized`**.

`objects=` overrides rule 3. It takes selectors of the form `name:kind` (optionally
`name:kind:namespace`) and moves those pod-less objects into a named resource. A selector that
matches several objects, or an object already in another resource, is an error at load.

Without `objects=` (a scratch copy of the Postgres half of the Tiltfile):

```
postgres      -> Service/postgres, StatefulSet/postgres
pgvector-init -> Job/pgvector-init
uncategorized -> Namespace/llm-testbench, Secret/postgres-credentials
```

With it, the real Tiltfile:

```
postgres      -> Namespace/llm-testbench, Secret/postgres-credentials, Service/postgres, StatefulSet/postgres
pgvector-init -> Job/pgvector-init
api           -> ServiceAccount/api, ConfigMap/api-config, Service/api, Deployment/api
api-secrets   -> local cmd: make k8s-secrets (watches .env)
```

Why it matters: step 3 enables resources by name, and nobody names `uncategorized`. Without
`objects=`, `make tilt-db` on a fresh cluster would apply a StatefulSet into a namespace that
does not exist, referencing a Secret that does not exist.

## Step 3 — Selection: which resources are enabled

All the resources from step 2 exist in Tilt. Only the **enabled** ones get work done:

- `tilt up` with no argument enables all of them.
- `tilt up postgres pgvector-init` (`make tilt-db`) enables the named ones **plus their
  `resource_deps`**. Verified: with `b` depending on `a`, `tilt ci -- b` ran `a` then `b`, and
  never ran `c`.
- From the UI, or with `tilt enable` / `tilt disable`, you change the set while Tilt runs. That
  path **ignores dependencies**: enabling `api` from the UI does not enable `api-secrets`.

For a **disabled** resource Tilt does nothing: no build, no apply, no command, no port forward,
no file watching. It stays in the UI, greyed out, with an "Enable" button.

"Disabled" describes Tilt's activity, not the cluster's content. Here is what the namespace
holds right now, with the owner label of each object:

```bash
kubectl -n llm-testbench get statefulset,deploy,job,svc,secret,configmap,sa -L app.kubernetes.io/managed-by
```
```
NAME                               AGE     MANAGED-BY      (other columns trimmed)
statefulset.apps/postgres          53d     tilt
deployment.apps/api                53d     Helm
job.batch/pgvector-init            3d19h   tilt
service/api                        53d     Helm
service/postgres                   53d     tilt
secret/postgres-credentials        53d     tilt
secret/sh.helm.release.v1.api.v1   53d
configmap/api-config               53d     tilt
serviceaccount/api                 53d     tilt
```

The `api` Deployment and Service are 53 days old and labelled `Helm`: they come from the
`helm upgrade --install` of guide 01 step 4, and the Helm release Secret
`sh.helm.release.v1.api.v1` confirms it. In the current Tilt session the `api` resource has
never been applied (step 4 explains why), yet a Deployment named `api` is running. Tilt does
not scan the cluster: **`kubectl` is the only source of truth about what runs.**

## Step 4 — Ordering: `resource_deps`

The dependency graph of this Tiltfile, as Tilt displays it:

```bash
tilt alpha tree-view
```
```
└── postgres (ok)
    ├── api (pending)
    ├── api-secrets (build error)
    │   └── api (pending)
    └── pgvector-init (ok)
```

A resource starts its first build only once all its dependencies are **ready**:

- a Kubernetes workload: its pod runs and all its containers are ready (probes included);
- a `Job`: it has completed;
- a `local_resource`: its command has succeeded at least once.

Each edge has a reason. `pgvector-init` runs `CREATE EXTENSION vector` and needs a live
database. `api-secrets` runs `kubectl -n llm-testbench create secret` and needs the namespace,
which belongs to `postgres` since the `objects=` change. `api` reads that Secret and the
database at startup.

The tree above shows a real failure. `.env` does not exist, so `make k8s-secrets` fails:

```bash
tilt logs api-secrets
```
```
Running cmd: make k8s-secrets
.env missing: copy .env.example
Build Failed: Command "make k8s-secrets" failed: exit status 2
```

and `api` waits, without even building its image:

```bash
tilt get uiresource api -o jsonpath='{.status.waiting}'
```
```
{"on":[{"kind":"UIResource","name":"api-secrets",...}],"reason":"waiting-for-dep"}
```

The limit to know: dependencies gate only the **first** build after `tilt up`. Once `postgres`
has been ready once, a Postgres restart neither holds back nor restarts `api`.

## Step 5 — Build: the image, for enabled resources only

When `api` is enabled and unblocked, Tilt builds the image that `docker_build` registered:

- **The context** is `.`, filtered by [`.dockerignore`](../../.dockerignore), which excludes
  `docs`, `infra`, `notebooks`, `tests`, `data` and `.env`.
- **The tag** is Tilt's, content-based (`tilt-<hash>`). The `tag: dev` of
  [`values-local.yaml`](../../infra/helm/llm-testbench-api/values-local.yaml) only makes the
  chart render: Tilt rewrites the `image:` field of every object that references
  `llm-testbench-registry:5050/llm-testbench-api` with the reference it just built. This is
  **image injection**, and it is why `docker_build` and `k8s_yaml` need no explicit link
  between them.
- **The registry** is found on its own, from a ConfigMap that k3d writes into every cluster it
  creates (a Kubernetes convention, KEP-1755):

```bash
kubectl -n kube-public get cm local-registry-hosting -o jsonpath='{.data}'
```
```
host: localhost:5050
hostFromClusterNetwork: llm-testbench-registry:5000
```

Tilt pushes to `host` from your Mac and gives the pod a reference the cluster can pull. After a
build, the reference actually used is visible in two places (not shown here: in the current
session `api` never got past step 4, so the status is empty):

```bash
tilt get imagemap llm-testbench-registry:5050_llm-testbench-api -o jsonpath='{.status.image}'
kubectl -n llm-testbench get deploy api -o jsonpath='{..image}'
```

With `make tilt-db`, `api` is disabled: no image build at all. That is the "without building
the API" of [Makefile:83](../../Makefile#L83).

## Step 6 — Apply: one apply per resource

When a resource is ready to deploy, Tilt applies all its objects together, in kind order:
namespace first, workload last, as the load result already lists them. On the way it stamps
them:

```bash
kubectl -n llm-testbench get pod postgres-0 -o jsonpath='{.metadata.labels}'
```
```
{"app":"postgres","app.kubernetes.io/managed-by":"tilt","tilt.dev/pod-template-hash":"bfbcf70d6b6df7b0617f",...}
```

- `app.kubernetes.io/managed-by: tilt` goes on every object, overriding the chart's own value:
  the chart sets `managed-by: {{ .Release.Service }}`, which renders `Helm`, yet `api-config`
  shows `tilt`.
- `tilt.dev/pod-template-hash` goes on pod templates, so Tilt can tell its pods from older
  ones.

Tilt applies the way `kubectl apply` does, client-side, recording a
`kubectl.kubernetes.io/last-applied-configuration` annotation on each object. That is the
mechanism behind guide 01's "two owners" pitfall: a `kubectl apply -k infra/k8s/local` on top
removes the labels Tilt added, the StatefulSet's pod template changes, and Postgres restarts.

After the apply, the resource's controllers take over. They watch its pods, stream their logs
into the UI, and keep the port forwards open: `PortForward/postgres-postgres-0` maps
`localhost:5432` to the pod, and Tilt reopens it when the pod is replaced.

## Step 7 — Watch: what Tilt does when a file changes

Tilt watches three sets of paths, the three `FileWatch` objects of this session:

| FileWatch | Watched paths | On change |
|---|---|---|
| `configs:(Tiltfile)` | `Tiltfile`, `Dockerfile`, `.dockerignore`, `.tiltignore`, the files of `infra/k8s/local/`, the chart and `values-local.yaml` | reload the Tiltfile (step 1 again); only the resources whose objects changed are applied again |
| `image:llm-testbench-registry:5050_llm-testbench-api` | `.` minus `.dockerignore` | live update or full rebuild of `api` |
| `local:api-secrets` | `.env` | rerun `make k8s-secrets` |

For a file inside the image context:

| File changed | What Tilt does |
|---|---|
| `src/**`, `prompts/**`, `config/**` | **live update**: copies the files into the running container (step 8) |
| anything else in the context: `pyproject.toml`, `uv.lock`, `Dockerfile`, `README.md`, `Makefile` | **full rebuild** of the image, then redeploy |
| a path listed in `.dockerignore` (`docs/`, `tests/`, `notebooks/`…) | nothing for the image |

Tilt does not read the Dockerfile's `COPY` lines. Editing the `Makefile` triggers a build even
though no layer uses it. Docker's cache makes that build take seconds, and an identical image
gets an identical tag, so the pod normally does not restart.

## Step 8 — Live update, precisely

`live_update=[sync('./src', '/app/src'), ...]` means: on a change under `src/`, find the running
containers built from this image and copy the changed files into them, over the Kubernetes
exec API (a `tar` stream unpacked in the container). No rebuild, no new pod: seconds instead
of a minute.

What `sync` does **not** do is restart anything. The container keeps running, and so does its
process. A Python process imports its modules once, at startup, and keeps them in memory: a new
file on disk changes nothing for it. The image's own command,
`uvicorn llm_testbench.app.main:app` ([Dockerfile:29](../../Dockerfile#L29)), stops there.

So the local values replace that command
([`values-local.yaml`](../../infra/helm/llm-testbench-api/values-local.yaml), `args`) with the
same one plus `--reload`. uvicorn then runs two processes: a reloader (PID 1) that watches
`/app/src`, `/app/prompts` and `/app/config`, and the server, a child it stops and starts again
on each change. The new server imports the new file: `uv sync` installs the project in editable
mode, so the venv in `/app/.venv` points at `/app/src`.

Two more settings make it work, both in the local values only:

- `--reload-include=*.md` and `--reload-include=*.toml`: by default uvicorn reloads on `*.py`
  changes only, and the prompts are `.md`, the config files `.toml`.
- `securityContext.readOnlyRootFilesystem: false`: the sync writes into `/app`, part of the
  image's filesystem, which the chart's production default mounts read-only.

The image and the cloud values are unchanged: production runs the plain command, read-only.

The synced files exist only in the running container. A container that restarts (a crash, a
`kubectl rollout restart`) comes back from the image, without them.

## Step 9 — Stopping: `Ctrl-C`, `tilt down`, disable

Three different actions, often confused:

| Action | Tilt side | Kubernetes objects | Namespace |
|---|---|---|---|
| `Ctrl-C` | Tilt and its port forwards stop | **kept**, the pods keep running | kept |
| `tilt down` | — | the objects of every resource in the Tiltfile are deleted | **kept** (`--delete-namespaces` to delete it) |
| disable (UI or `tilt disable x`) | the resource stops | the objects **of that resource** are deleted | **deleted**, if the resource owns it |

The last cell was verified on a throwaway namespace. A resource `x` owning `Namespace/tilt-exp`
and a ConfigMap: `tilt disable x` deletes the ConfigMap and puts the namespace in
`Terminating`. With the annotation `tilt.dev/down-policy: keep` on the Namespace, the same
disable deletes the ConfigMap and leaves the namespace `Active`.

What none of the three deletes:

- **Objects Tilt did not apply in this session.** The Helm-installed `api` of step 3, and
  objects left by an earlier session: started with `x` disabled, Tilt left in place the
  ConfigMap a previous session had applied.
- **What a `local_resource` command created.** `llm-testbench-api-secrets` is made by `kubectl`
  inside `make k8s-secrets`; Tilt never sees it.
- **The Postgres PVC `data-postgres-0`.** The StatefulSet controller creates it from
  `volumeClaimTemplates`, not Tilt, so the data survives `tilt down`. It does not survive the
  deletion of its namespace.

## Run — replay the claims

**1. The load alone**, no deployment: the `tilt alpha tiltfile-result` command of step 1.
Expected: the four resources and their dependencies.

**2. The cluster, not the UI**: the `kubectl ... -L app.kubernetes.io/managed-by` command of
step 3. Expected after `make tilt-db` on a fresh cluster: only `tilt` objects, no `api`.

**3. Dependencies on the command line**, in a scratch directory, on a second Tilt:

```bash
mkdir -p /tmp/tilt-deps && cd /tmp/tilt-deps
cat > Tiltfile <<'EOF'
local_resource('a', cmd='echo A-RAN')
local_resource('b', cmd='echo B-RAN', resource_deps=['a'])
local_resource('c', cmd='echo C-RAN')
EOF
tilt ci --port 10351 --timeout 60s -- b
```

Expected: `A-RAN`, then `B-RAN`, no `C-RAN`, then `SUCCESS. All workloads are healthy.`

**4. Leftovers and disable**, on a throwaway namespace of the k3d cluster:

```bash
mkdir -p /tmp/tilt-disable && cd /tmp/tilt-disable
cat > Tiltfile <<'EOF'
k8s_yaml(blob('''
apiVersion: v1
kind: Namespace
metadata:
  name: tilt-exp
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: probe
  namespace: tilt-exp
data:
  k: v
'''))
k8s_resource(new_name='x', objects=['tilt-exp:namespace', 'probe:configmap'])
local_resource('y', cmd='echo Y')
EOF
tilt ci --port 10351 --timeout 60s -- x    # session 1 applies x, then exits
tilt up --port 10351 -- y                  # session 2, x disabled (leave it running)
```

In a second terminal:

```bash
kubectl -n tilt-exp get cm probe           # still there: session 2 did not clean it up
tilt enable --port 10351 x
tilt wait --port 10351 --for=condition=Ready uiresource/x
tilt disable --port 10351 x
kubectl get ns tilt-exp                    # Terminating
```

Then add `annotations: {tilt.dev/down-policy: keep}` under the Namespace's `metadata` (Tilt
reloads the file), enable and disable `x` again: the namespace stays `Active`. Clean up with
`Ctrl-C` in the first terminal, then `kubectl delete ns tilt-exp`.

**5. Sync and reload under Tilt**, once `.env` exists and `make tilt-up` is green. Change the
value returned by `/healthz` in
[`src/llm_testbench/app/main.py`](../../src/llm_testbench/app/main.py) and save. Expected:
`tilt logs api` shows the sync, then uvicorn's
`WatchFiles detected changes in 'src/llm_testbench/app/main.py'. Reloading...`, and
`curl -s localhost:8000/healthz` returns the new value. Not observed under Tilt yet: `api` has
never run in this cluster's Tilt session. Run 6 replays the same mechanism without a cluster.

**6. Sync and reload on the image alone**, with Docker, the sync done the way Tilt does it
(`tar` through `exec`). From the repo root:

```bash
docker build -t llm-testbench-api:reload-test .
docker run -d --name rt llm-testbench-api:reload-test \
  uvicorn llm_testbench.app.main:app --host=0.0.0.0 --port=8000 --reload --reload-dir=/app/src
mkdir -p /tmp/rt/app/src/llm_testbench/app
sed 's/return {"status": "ok"}/return {"status": "reloaded"}/' src/llm_testbench/app/main.py \
  > /tmp/rt/app/src/llm_testbench/app/main.py
tar -cf - -C /tmp/rt app/src/llm_testbench/app/main.py | docker exec -i rt tar -C / -xf -
docker logs rt 2>&1 | grep WatchFiles      # a second later
docker exec rt python -c "import urllib.request as u; print(u.urlopen('http://localhost:8000/healthz').read())"
docker rm -f rt
```

Expected (observed on 2026-10-26):

```
WARNING:  WatchFiles detected changes in 'src/llm_testbench/app/main.py'. Reloading...
b'{"status":"reloaded"}'
```

Variants with the same sync, observed the same day:

| Container | Result after the sync |
|---|---|
| the image's own command (no `--reload`) | `{"status":"ok"}`: the file changed, the old code serves |
| the local values' `args`, a `.md` and a `.toml` synced | `WatchFiles detected changes in 'config/llm_pricing.toml', 'prompts/chat_answer.md'. Reloading...` |
| `--reload` without the two `--reload-include`, same files | no reload |
| the image's own command, `docker run --read-only --tmpfs /tmp` (the production default) | the sync fails: `tar: app/src/llm_testbench/app/main.py: Cannot open: File exists` |

## Pitfalls

1. **Sync is not reload.** A `live_update` made only of `sync()` steps copies files and
   restarts nothing, and a Python process keeps the modules it imported. This repo shipped
   that way, untested: the Tiltfile header promised "uvicorn --reload does the rest", guide 01
   "a pod restart by Tilt", and neither existed. Behind it hid a second bug: with the chart's
   read-only root filesystem, the sync itself failed. Both are fixed in the local values
   (step 8) and checked by run 6.
2. **Disabling `postgres` deletes the namespace. Open in this repo.** Since `objects=` gave the
   namespace to `postgres`, disabling `postgres` in the UI deletes `llm-testbench` and
   everything in it: the API, `llm-testbench-api-secrets`, and the PVC with the indexed data.
   The `local-path` StorageClass reclaims with `Delete`, so the volume goes too. `tilt down`
   does not have the problem, since it keeps namespaces. The fix tested in step 9 is the
   `tilt.dev/down-policy: keep` annotation on the Namespace.
3. **Helm and Tilt on the same objects.** Guide 01 step 4 installs the chart with `helm upgrade
   --install`, and Tilt then applies the same objects rendered by `helm template`. The cluster
   today shows the result: a release Helm believes it owns, objects labelled half `Helm`, half
   `tilt`. `helm uninstall api` would delete objects Tilt manages, and `tilt down` leaves the
   release Secret behind. After that manual step, `helm uninstall api -n llm-testbench`
   before `make tilt-up`.
4. **`uncategorized` has no dependencies.** Any pod-less object left there is applied as soon as
   Tilt starts, whatever its workload waits for, and is never applied by
   `tilt up <names>`. Every pod-less object should be claimed with `objects=`.
5. **The UI ignores dependencies.** Enabling `api` from the UI does not enable `api-secrets`.
   From a `make tilt-db` session, `tilt enable api-secrets api` turns it into a `make tilt-up`
   session without restarting Tilt (`postgres` is already running).
6. **`Ctrl-C` leaves everything running.** The pods keep consuming the Docker VM's memory; only
   the port forward on 5432 stops (`make pg-port-forward` brings it back).
7. **One Tilt per port.** A second `tilt up` in the same repo collides on port 10350; that is why
   guide 01 says to stop `make tilt-db` before `make tilt-up`, and why the experiments above use
   `--port 10351`.
8. **`--reload` watches `*.py` only.** Without `--reload-include`, a prompt (`.md`) or a config
   file (`.toml`) is synced and nothing restarts (run 6).
9. **The local pod is writable, the cloud one is not.** The sync needs
   `readOnlyRootFilesystem: false` locally, so code that writes outside `/tmp` works under Tilt
   and fails on EKS (guide 06, pitfalls). `docker run --read-only --tmpfs /tmp` on the image
   reproduces the cloud constraint on the Mac.

## Interview questions

<details><summary><b>1. What does Tilt do with a Helm chart, and how is it different from <code>helm upgrade --install</code>?</b></summary>

Tilt runs `helm template` at load time and applies the rendered YAML itself, like any other
manifest: there is no Helm release, no release history, no `helm rollback`, and `helm list`
does not show it. Tilt owns the objects (`managed-by: tilt`). Mixing both tools on the same
release gives two owners: `helm uninstall` deletes objects Tilt manages, and Tilt overwrites
what Helm applied.
</details>

<details><summary><b>2. A developer saves a file, Tilt reports a successful live update, the API still serves the old behavior. Why, and what are the fixes?</b></summary>

`sync` copies files into the running container; it does not restart the process, and a Python
process keeps the modules it imported in memory. Two fixes: restart the process after the sync
from the Tilt side (the `restart_process` extension and its `docker_build_with_restart`, which
wraps the image's entrypoint in dev), or have the app reload itself (`uvicorn --reload`, a
dev-only command). This repo does the second, in the local chart values: no third-party
extension, and the image stays the production one. Either way the container must accept the
write: with a read-only root filesystem, the sync itself fails.
</details>

<details><summary><b>3. Why do a Namespace and a Secret need <code>objects=</code> in this Tiltfile?</b></summary>

Tilt groups objects into resources around workloads; a Namespace or a Secret creates no pod, so
it lands in `uncategorized`. `tilt up postgres pgvector-init` enables only the named resources,
so without `objects=` the StatefulSet would be applied without its namespace and its Secret.
`objects=` attaches them to `postgres`, and Tilt applies the namespace first within the
resource.
</details>

<details><summary><b>4. What does <code>resource_deps</code> guarantee, and what does it not?</b></summary>

It guarantees that a resource's first build waits until its dependencies are ready: pod running
with ready containers, Job completed, or command succeeded. It does not order anything after
that first build: a dependency that restarts does not block or restart its dependents. And
enabling a resource from the UI does not enable its dependencies.
</details>

<details><summary><b>5. Difference between <code>Ctrl-C</code>, <code>tilt down</code> and disabling a resource? Which one can lose the database here?</b></summary>

`Ctrl-C` stops Tilt and leaves everything running in the cluster. `tilt down` deletes the
objects of all the resources but keeps namespaces by default, so the Postgres PVC survives.
Disabling one resource deletes that resource's objects, its namespace included if it owns it.
Here `postgres` owns `llm-testbench`: disabling it deletes the namespace, hence the PVC, hence
the data, unless the Namespace carries `tilt.dev/down-policy: keep`.
</details>

<details><summary><b>6. How does Tilt know where to push images on a k3d cluster?</b></summary>

k3d writes a `local-registry-hosting` ConfigMap in `kube-public` (the KEP-1755 convention) with
the address of the registry seen from the host and from the cluster. Tilt reads it, pushes to
the host address, and injects into the pod spec a reference the cluster can pull. No
`default_registry()` in the Tiltfile, and no credentials.
</details>

## What we did not do, and why

- **No Tilt extension**: `restart_process` was the other fix for pitfall 1. `uvicorn --reload`
  does the job without third-party code downloaded when the Tiltfile loads.
- **No `config.parse` or custom Tilt arguments**: the two profiles (`make tilt-db`,
  `make tilt-up`) are lists of resources, which `tilt up <names>` already covers.
- **No `.tiltignore`**: `.dockerignore` already filters the image context, and the other
  watches are explicit files.
- **No `tilt ci` in GitHub CI**: it needs a cluster, and the test CI stays offline (ADR 003).
- **No manual trigger mode**: automatic updates are the point of the loop, and with a single
  developer there is nothing to protect.

## Glossary

- **Tiltfile**: the Starlark program that declares what Tilt manages; evaluated at load, and
  again when one of its inputs changes.
- **Starlark**: a Python dialect for configuration; no I/O except through the functions Tilt
  provides (`kustomize`, `helm`, `local`…).
- **Resource**: Tilt's unit of work: objects applied together, one status, one row in the UI.
- **Workload**: a Kubernetes object that creates pods (`Deployment`, `StatefulSet`, `Job`,
  `DaemonSet`…).
- **`uncategorized`**: the catch-all resource for pod-less objects that no `objects=` claims.
- **Enabled / disabled**: whether Tilt works on a resource; says nothing about what is in the
  cluster.
- **`resource_deps`**: makes a resource's first build wait for other resources to be ready.
- **Image injection**: Tilt rewriting the `image:` fields with the reference it just built.
- **Live update**: updating a running container in place instead of rebuilding; `sync` copies
  files, `run` executes a command in the container. Neither restarts the process.
- **`tilt.dev/down-policy: keep`**: an annotation that keeps an object through `tilt down` and
  through disabling its resource.
- **KEP-1755, `local-registry-hosting`**: the convention by which a local cluster advertises
  its registry to tools like Tilt.
