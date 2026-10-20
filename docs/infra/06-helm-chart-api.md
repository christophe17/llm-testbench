# Guide 06 — The API Helm chart: probes, resources, HPA, PDB, secrets, security

**Duration**: 20 minutes of reading, 5 of execution. **Prerequisites**: guide 01 (local
cluster). **Cost**: €0. **Code**: `infra/helm/llm-testbench-api/`.

---

## The problem

Everyone knows how to deploy a container. Deploying it so that it **survives** an
update, a node failure, a traffic spike and a modified configuration file
— with no human intervention — is what a production-grade chart encodes.
Every default value in `values.yaml` answers a classic incident.

## The options

| Option | Verdict |
|---|---|
| Raw YAML manifests | Readable, but duplicated between local and cloud, and with no clean parameterization. |
| Kustomize | Good for simple overlays (we use it for local Postgres); weak for conditional logic (ExternalSecret or not, HPA or not). |
| **Helm** | **Chosen**: one chart, one values file per environment, conditions. The standard of the teams you will join. |
| An off-the-shelf generic chart | Hides the choices we want to explain here. Ours is 180 lines of templates. |

## Guided reading of the real code

**[`values.yaml`](../../infra/helm/llm-testbench-api/values.yaml)**, from top to bottom:

- **`replicaCount: 2`** — two replicas minimum: a single pod means zero fault
  tolerance and zero updates without downtime.
- **`config`** — the *non-secret* environment variables, rendered into a `ConfigMap`.
- **`secrets.existingSecret`** — the chart never creates a secret; it references one.
  Locally, `make k8s-secrets` creates it from `.env`. In the cloud,
  `secrets.externalSecret.enabled: true` renders an `ExternalSecret` that asks External
  Secrets Operator to build it from Secrets Manager (guide 05).
- **`resources`** — `requests` (what the scheduler reserves) and a memory limit,
  **but no CPU limit**: the CPU limit triggers CFS throttling that degrades
  latency without protecting anyone; the memory limit, on the other hand, keeps a leaking pod
  from taking the node down with it.
- **`autoscaling`** — an HPA on CPU (70%), from 2 to 6 replicas. It needs
  `metrics-server` (managed add-on on EKS, guide 03; shipped with k3s locally).
- **`podDisruptionBudget: minAvailable 1`** — during a node drain (update, scale
  down), Kubernetes will never evict the last available pod.
- **`probes`** — three probes, three questions (guide 01, question 1). The `startupProbe` at
  30 × 2 s gives 60 s to the Postgres pool and the schema; without it, an impatient liveness
  probe would kill a pod mid-startup, in a loop.
- **`podSecurityContext` / `securityContext`** — non-root, no privilege escalation,
  read-only filesystem (hence the `/tmp` volume as an `emptyDir`), all
  Linux capabilities dropped, default seccomp profile. This is the "restricted" level of the
  Pod Security Standards.

**[`templates/deployment.yaml`](../../infra/helm/llm-testbench-api/templates/deployment.yaml)**:

- **`strategy.rollingUpdate: maxUnavailable 0, maxSurge 1`** — an update creates the
  new pod before removing the old one: never fewer replicas than requested.
- **`checksum/config`** — the hash of the `ConfigMap` in the pod annotations: when
  the configuration changes, the hash changes, the Deployment rolls out again. Without it, a
  `helm upgrade` that only touches the configuration restarts nothing, and the new
  setting is never read.
- **`envFrom`** — the `ConfigMap` and the `Secret` (marked `optional`, so that the API
  starts and reports itself what it is missing via `/readyz`).
- **`topologySpreadConstraints`** — spread the replicas across different nodes when
  possible (`ScheduleAnyway`: locally, a single node, we block nothing).
- **`automountServiceAccountToken: false`** — the API does not call the Kubernetes API; a
  token mounted by default would be a free attack surface.

**[`templates/externalsecret.yaml`](../../infra/helm/llm-testbench-api/templates/externalsecret.yaml)**
— rendered only if enabled: for each `data` entry, a key of the target `Secret`
fed by a Secrets Manager key; and, if `database.masterSecretArn` is set, a
template that composes the database URL in the cluster (guide 05). `creationPolicy: Owner`:
the `Secret` belongs to the `ExternalSecret`, it disappears with it.

**The two values files.** `values-local.yaml`: image from the local registry, one
replica, no HPA or PDB, database URL pointing at the namespace's `postgres` service.
`values-dev.yaml`: ECR image at the git SHA, External Secrets, the `database` block (address and
ARN of the RDS secret, filled in by `make deploy` or the guide 09 workflow), pod identity
for Bedrock (guide 03).

## Run

**1. Lint and render**, before any deployment:

```bash
make helm-lint
helm template api infra/helm/llm-testbench-api -f infra/helm/llm-testbench-api/values-local.yaml | less
```

Read the rendered output: it is exactly what the cluster will receive. Look for `checksum/config`,
`readOnlyRootFilesystem`, `maxUnavailable`.

**2. Deploy locally** (guide 01, step 4) then observe the probes:

```bash
kubectl -n llm-testbench describe pod -l app.kubernetes.io/instance=api | sed -n '/Liveness/,/Environment/p'
kubectl -n llm-testbench get events --sort-by=.lastTimestamp | tail -5
```

**3. Trigger a zero-downtime update**: change `LLM_TESTBENCH_RETRIEVAL_K`
in `values-local.yaml`, rerun `helm upgrade`, and watch `kubectl get pods -w`: a
new pod is born, becomes ready, the old one stops. The checksum annotation did the
work.

**4. Trigger a liveness restart**: `kubectl -n llm-testbench exec <pod> --
kill 1` terminates uvicorn; the container restarts (`RESTARTS` goes to 1). No
`kubectl delete` needed.

## Pitfalls

- **A modified `ConfigMap` restarts nothing** without the checksum annotation. The classic
  symptom: "I changed the config, it changed nothing".
- **The CPU limit** is the most often copy-pasted and most often harmful setting:
  throttling appears well before the pod reaches its limit, on short spikes.
- **An HPA without `metrics-server`** stays at `<unknown>` and does nothing, silently.
  `kubectl get hpa` must display a percentage, not `<unknown>`.
- **`readOnlyRootFilesystem` breaks libraries that write** into their own folder
  (model caches, temporary files). The `/tmp` volume covers the common case; a
  local model (phase 6) will need a dedicated volume.
- **The PDB can block a drain** if `minAvailable` cannot be satisfied (a single
  replica with `minAvailable: 1`). The local values disable it for that reason.
- **`helm upgrade --wait` times out** if readiness never passes: it is not the
  chart, it is the API refusing traffic (guide 01, step 4).

## Interview questions

<details><summary><b>1. Why requests without a CPU limit?</b></summary>

Requests serve placement (the scheduler reserves) and priority under
contention. The CPU limit imposes a hard cap per scheduling period (CFS) and
causes throttling as soon as a spike exceeds the quota, even if the node has free CPU.
For a latency-sensitive service, you reserve without capping. Memory, on the other hand,
cannot be shared: you limit it so that a pod does not kill its neighbors.
</details>

<details><summary><b>2. What happens during a rolling update with maxUnavailable 0?</b></summary>

Kubernetes creates a pod of the new version (surge), waits for it to be ready (readiness),
then terminates an old pod; and starts again until the last one. Capacity never drops
below the requested count. The price: temporarily one extra replica, hence a bit
of node capacity held in reserve.
</details>

<details><summary><b>3. PDB and HPA: which protects against what?</b></summary>

The HPA adjusts the number of replicas to the load (scaling up and down). The PDB limits
*voluntary* evictions (drain, node update): it does not protect against a hardware
failure. The two combine: the HPA sets how many pods, the PDB how many can
disappear at the same time.
</details>

<details><summary><b>4. How does the pod get its secrets without them being in git?</b></summary>

The chart references a `Secret` by name. Who creates it depends on the environment: a
human from `.env` locally, External Secrets Operator from Secrets Manager in the cloud,
authenticated by the pod identity (no AWS key in the cluster). The chart is the same.
</details>

<details><summary><b>5. Why a startupProbe when we already have a liveness probe?</b></summary>

A liveness probe strict enough to detect a hang in production (a few tens of
seconds) is too strict for a slow startup (connection pool, loading a
model). The startupProbe grants a generous delay at startup only, then hands
over to the strict liveness probe. Without it: restart loops at startup.
</details>

## What we did not do, and why

- **No Ingress or TLS** by default: exposure depends on the environment (guide
  03 for EKS); the template exists, disabled.
- **No NetworkPolicy**: to add with the SQL/API sources of phase 4, when there
  are flows to restrict.
- **No PriorityClass or Karpenter**: a single service, a single node group;
  phase 5, with the traffic generator.
- **No automated chart tests** (helm-unittest): `helm lint` + rendering are enough
  at this stage; to revisit when the chart has more than one variant.
