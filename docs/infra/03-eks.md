# Guide 03 — EKS: control plane, Graviton nodes, access, pod identities, deployment

**Duration**: 45 minutes, ~20 of them waiting on Terraform. **Prerequisites**: guides 00
to 02. **Cost**: ~$0.25/h when on (environment README); **`make infra-down` at the end of
the session**. **Code**: `infra/terraform/envs/dev/eks.tf`, `iam.tf`, `outputs.tf`,
targets `make infra-up`, `kubeconfig`, `cluster-addons`, `deploy`.

---

## The problem

Running Kubernetes yourself is something you know how to do. The question on AWS is *what
you delegate*: the control plane (EKS manages it, $0.10/h), the nodes (managed groups,
Fargate, or Auto Mode), the add-ons (CNI, DNS, proxy, metrics), and above all **how a pod
gets AWS permissions** without a shared key — the point that trips everyone up and the
first interview question about EKS.

## The options

**The nodes.**

| Option | Verdict |
|---|---|
| **Managed node group** (Graviton `t4g.medium`) | **Chosen**: AWS manages the AMI and updates, we keep control of sizing. Graviton: ~20% cheaper than x86 and **the same architecture as the image built on an M1 Mac** — no cross-build. |
| Fargate | No node to manage, but slow startup, no volumes, no DaemonSet: a poor fit for an API with probes and for Langfuse. |
| EKS Auto Mode | Karpenter and the add-ons managed by AWS, billed extra per node. Tempting, but it hides precisely what we want to learn here. |

**Pod identities.**

| Option | Verdict |
|---|---|
| AWS key in a Secret | Never: a shared key, with no expiry, inside the cluster. |
| IRSA (role per ServiceAccount via OIDC) | The former standard, still required by some charts; annotation on the ServiceAccount, one OIDC provider per cluster. |
| **EKS Pod Identity** | **Chosen**: an association (cluster, namespace, ServiceAccount) → role, created by Terraform; no annotation, no OIDC to manage. The agent is an add-on. |

**Human access to the cluster.**

| Option | Verdict |
|---|---|
| `aws-auth` ConfigMap | On its way out; courses still teach it. |
| **Access entries** (`authentication_mode = "API"`) | **Chosen**: access rights are AWS resources, not YAML inside the cluster. |

## Guided reading of the real code

**[`eks.tf`](../../infra/terraform/envs/dev/eks.tf)**:

- `kubernetes_version = "1.33"`: each version gets ~14 months of standard support, then
  **extended support is billed** at six times the price. A variable, to upgrade
  deliberately.
- `endpoint_public_access` + `endpoint_private_access`: the Kubernetes API is reachable
  from your Mac (public, filtered by `public_access_cidrs`) and from the nodes (private).
- `authentication_mode = "API"` and `enable_cluster_creator_admin_permissions = true`:
  the identity that runs `terraform apply` becomes cluster administrator through an access
  entry — this is what makes `kubectl` possible as soon as the apply finishes.
- `access_entries`: the GitHub Actions deployment role (bootstrap, `github.tf`) receives
  `AmazonEKSClusterAdminPolicy` on the dev cluster — this is what lets the guide 09
  workflow run `helm upgrade`. Least privilege (`AmazonEKSEditPolicy` scoped to the
  namespace, plus a ClusterRole for the External Secrets CRDs) is discussed there.
- `enable_irsa = true`: the OIDC provider exists anyway, for charts that do not speak Pod
  Identity yet.
- `create_kms_key = true`: encryption of Kubernetes secrets at rest with a dedicated KMS
  key (~$1/month).
- `enabled_log_types`: control plane logs (API, audit, authentication) in CloudWatch, kept
  7 days.
- `addons`: the five managed add-ons. `before_compute = true` for the CNI and the Pod
  Identity agent: they must exist before the nodes, otherwise the first pods start without
  networking or without identity. **`metrics-server` as a managed add-on**: it is what the
  chart's HPA (guide 06) queries.
- `eks_managed_node_groups.default`: Amazon Linux 2023 **arm64** AMI, `t4g.medium`
  (2 vCPU, 4 GB), 1 to 3 nodes, 2 at startup, 30 GB disk.

**[`iam.tf`](../../infra/terraform/envs/dev/iam.tf)** — the part to read slowly:

- `pod_identity_trust`: the trust policy every Pod Identity role carries — the
  `pods.eks.amazonaws.com` service can assume the role and tag the session.
- `api` role: `bedrock:InvokeModel` and `InvokeModelWithResponseStream` on the region's
  foundation models and on the `eu.*` inference profiles (Claude models in Europe are often
  served through an EU cross-region profile). Nothing else.
- `external_secrets` role: read the secrets under the `llm-testbench/dev/*` prefix, and
  only those.
- Two `aws_eks_pod_identity_association`: (namespace `llm-testbench`, ServiceAccount
  `api`) → API role; (namespace `external-secrets`, ServiceAccount `external-secrets`)
  → ESO role. The API's ServiceAccount name is the Helm release name (`api`), hence
  `var.api_service_account`.

**[`outputs.tf`](../../infra/terraform/envs/dev/outputs.tf)** — what the `make` targets
consume: the ECR URL, the `update-kubeconfig` command, the names of the secrets to fill in.

## Run

**1. Create the environment** (~20 minutes; the EKS control plane is the long part).

```bash
make infra-up
```

Answer `yes`. At the end, the Makefile chains `make kubeconfig`. Check:

```bash
kubectl config current-context           # arn:aws:eks:eu-west-3:<account>:cluster/llm-testbench-dev
kubectl get nodes -o wide                 # 2 nodes Ready, ARCH arm64
kubectl get pods -A                       # coredns, kube-proxy, aws-node, eks-pod-identity-agent, metrics-server
kubectl top nodes                         # metrics-server responds
```

**2. The add-ons outside Terraform**: External Secrets Operator (Helm) and the secret store.

```bash
make cluster-addons
kubectl -n external-secrets get pods
kubectl get clustersecretstore aws-secrets-manager     # READY True
```

`READY True` proves the whole chain: the ESO pod obtained, through Pod Identity, temporary
credentials allowing it to list our secrets. No key was created anywhere.

**3. Fill in the secrets** (guide 05, to do now if you want a working `/chat`) then
**deploy the API**:

```bash
make deploy
kubectl -n llm-testbench get pods -w
```

`make deploy`: ECR login, image build (arm64, like the nodes), push tagged with the git
SHA, `helm upgrade` with `values-dev.yaml`. As locally, the pod will stay `0/1` as long as
the index does not exist in RDS: that is guide 04.

**4. Check the API's pod identity**, without a key:

```bash
kubectl -n llm-testbench exec deploy/api -- env | grep AWS_CONTAINER_CREDENTIAL_FULL_URI
```

This variable, injected by the Pod Identity agent, is where the AWS SDK will go to fetch
temporary credentials for the `api` role. The LLM layer's Bedrock provider (`bedrock`
backend, `config/llm_backends.toml`) uses it as is.

**5. At the end of the session:**

```bash
make infra-down
```

Check Cost Explorer the next day: nothing should appear apart from the secrets (cents) and,
possibly, leftover CloudWatch logs.

## Pitfalls

- **EKS extended support**: a version that moves into extended support costs $0.60/h
  instead of $0.10/h, with no warning other than an email. Upgrade the version before the
  deadline (the variable exists for that).
- **`before_compute`**: if forgotten, the first nodes start before the CNI, the system pods
  fail, then everything eventually converges — after twenty minutes of confusion.
- **The creator's access entry**: if `terraform apply` is run by a different identity from
  your `kubectl` one (an assumed role, for example), you will not have access to the
  cluster. Add `access_entries` for the other identities.
- **Pod Identity only works for pods launched after the association**. A pod already
  running does not receive the identity: restart it.
- **An amd64 image on Graviton nodes** does not start (`exec format error`). The Mac image
  is arm64; if you move to x86 nodes, `docker buildx build --platform linux/amd64`.
- **`make infra-down` can fail on resources created by Kubernetes** (a LoadBalancer, EBS
  volumes) that Terraform does not know about. Delete the LoadBalancer-type Services and the
  PVCs first, then rerun.
- **Control plane CloudWatch logs** persist after destruction (log group with 7-day
  retention): a few cents, but visible on the bill.

## Interview questions

<details><summary><b>1. How does a pod get AWS permissions, and why not a key?</b></summary>

Through a pod identity: the pod's ServiceAccount is associated with an IAM role, the agent
on the node provides temporary credentials that the SDK picks up automatically. A static
key does not expire, is shared among all the pods that read it, and leaks with any
`kubectl get secret`. Two mechanisms: IRSA (OIDC, annotation on the ServiceAccount) and Pod
Identity (AWS association, no annotation), the second gradually replacing the first.
</details>

<details><summary><b>2. Access entries versus aws-auth?</b></summary>

`aws-auth` is a ConfigMap inside the cluster that maps IAM identities to Kubernetes groups:
modifiable by anyone who edits the ConfigMap, invisible to IAM, easy to break (one YAML
error and nobody gets in anymore). Access entries are AWS resources managed through the API,
with predefined policies (admin, view…), audited by CloudTrail.
</details>

<details><summary><b>3. When do you choose Fargate, a managed group, or Karpenter?</b></summary>

Fargate for isolated workloads, with no DaemonSet or volume, where you want no node to
manage at all. A managed group for a stable cluster of predictable size. Karpenter when the
load varies and the instance choice (family, Spot) must be made on demand: it is the keyword
in job postings, and the topic of phase 5 when there is traffic to absorb.
</details>

<details><summary><b>4. What does the EKS price include?</b></summary>

$0.10/h for the control plane whatever the size, then the nodes at the EC2 rate, EBS
storage, the NAT, the load balancers, and $0.60/h under extended support. The control plane
alone is ~$73/month: that is why a dev cluster must be shut down.
</details>

<details><summary><b>5. How do you expose a service on EKS?</b></summary>

A `Service type: LoadBalancer` creates a load balancer (classic by default, NLB/ALB with the
AWS Load Balancer Controller) in the subnets tagged `kubernetes.io/role/elb`. An Ingress
requires the controller. Each load balancer costs ~$0.02/h: in dev, port-forward is enough.
</details>

## What we did not do, and why

- **No Karpenter**: a fixed node group is enough as long as there is no variable load
  (phase 5).
- **No AWS Load Balancer Controller or Ingress**: port-forward in dev; public exposure will
  come with the chat UI (phase 5).
- **No Spot**: Spot nodes cost ~70% less but can disappear; relevant for the traffic
  generator or the evaluation jobs, not for the API in phase 1.
- **No IAM Identity Center**: a single human on a personal account; the production answer
  stays noted (guide 00).
- **The deployment pipeline is in guide 09** (since 2026-10-19): `make deploy` from the
  workstation, and the same deployment through GitHub Actions with an OIDC role; the test CI
  stays offline (ADR 003).
- **No restriction of the public endpoint to one IP**: `public_access_cidrs` stays open, and
  that is a decision (ADR 009) — the pipeline deploys from GitHub runners with variable IPs,
  and authentication is IAM (access entries, audit logs). The day deployment moves to pull
  mode (GitOps) or to a runner inside the VPC, we close it; until then,
  `TF_VAR_public_access_cidrs='["your.ip/32"]'` if you only deploy from your workstation.
