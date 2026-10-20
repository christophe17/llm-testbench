# Guide 09 — Deployment with GitHub Actions and OIDC: arm64 build, ECR, Helm, no key

**Duration**: 20 minutes, 5 of them waiting for the workflow. **Prerequisites**: guides 00
(bootstrap applied, with `github.tf`), 03 (cluster up) and 05 (secrets set). **Cost**: €0 (GitHub
Actions minutes are free on a public repository; the cluster costs what it
costs — guide 08). **Code**: `infra/terraform/bootstrap/github.tf`,
`infra/terraform/envs/dev/eks.tf` (`access_entries`), `.github/workflows/deploy.yml`, the
`make deploy` and `make deploy-trigger` targets.

---

## The problem

`make deploy` works, but it works *from your workstation*: with your credentials, your
Docker, your `kubectl`. A deployment pipeline must do the same thing from a machine
that has nothing, and that above all must not receive an AWS key with an unlimited lifetime
in a GitHub secret: that is the most classic leak in the industry (a `print(os.environ)` in
a CI log). The question is not "how to deploy from CI", it is **how CI
proves who it is** without a key.

## The options

| Option | Verdict |
|---|---|
| AWS access key in GitHub secrets | Never: long-lived key, visible to every workflow in the repository, with no trace of *which* job used it. |
| **OIDC: GitHub issues a signed token, AWS exchanges it for a role** | **Chosen**: temporary credentials (one hour), role restricted to the repository and the branch, every assume-role in CloudTrail with the token's `sub`. Zero stored secrets. |
| Pull-mode deployment (GitOps: Argo CD, Flux) | The production answer when the cluster endpoint is private: nothing comes in, the cluster pulls. One more operator on an ephemeral cluster; noted for phase 5 (canary, Argo Rollouts). |
| Self-hosted runner in the VPC | Solves the private endpoint, adds a machine to operate. No. |

## Guided reading of the real code

**[`github.tf`](../../infra/terraform/bootstrap/github.tf)** — three resources, in the
bootstrap because they are account identities, stable, free, and they must
survive the evening's `make infra-down`:

- `aws_iam_openid_connect_provider.github`: AWS learns to trust tokens signed
  by `token.actions.githubusercontent.com`, for the audience `sts.amazonaws.com`. Only one per
  account (the URL is the key): if another project has already created it, import it instead
  of recreating it.
- `github_deploy_trust`: the role's trust policy. Two conditions, and that is the whole
  security model: the audience, and the token's `sub`, which must equal
  `repo:christophe17/llm-testbench:ref:refs/heads/main`. **Neither a fork, nor a pull request,
  nor another branch** can assume this role — a PR's `sub` is
  `repo:...:pull_request`, a branch's is `ref:refs/heads/<name>`.
- `github_deploy`: the role's policy, kept as tight as possible. `ecr:GetAuthorizationToken`
  on `*` (the API knows nothing finer), push to **the** `llm-testbench-api` repository and
  nothing else, `eks:DescribeCluster` on **the** cluster (that is what `update-kubeconfig`
  does), and `rds:DescribeDBInstances` on **the** instance, to read the database address and
  its secret's ARN without touching the Terraform state. No `terraform` in the pipeline: it
  deploys an image, it does not manage the infra.

**[`eks.tf`](../../infra/terraform/envs/dev/eks.tf)**, `access_entries` block — IAM says *who*
can call the EKS API, not what one can do *inside* Kubernetes. The access entry maps the ARN
of the role (rebuilt from its name, since the bootstrap and `envs/dev` share no
state) to the `AmazonEKSClusterAdminPolicy` policy on the whole cluster. That is too much for a
`helm upgrade` in one namespace, and it is a deliberate choice for a single-tenant dev cluster;
the least-privilege answer is in the pitfalls.

**[`deploy.yml`](../../.github/workflows/deploy.yml)** — what `make deploy` does, step by
step, with these differences:

- `on: workflow_dispatch` only: the cluster is ephemeral, an automatic deployment on
  every push would fail in the evening. `concurrency: deploy-dev`: never two interleaved
  deployments.
- `permissions: id-token: write`: this is what allows the job to request an OIDC token.
  Without this line, `configure-aws-credentials` fails with a message that talks about
  everything except that. `vars.AWS_DEPLOY_ROLE_ARN` is a repository *variable*, not a secret:
  an ARN is not confidential.
- `runs-on: ubuntu-24.04-arm`: an arm64 runner, free for a public repository. The image is
  built natively for the Graviton nodes, without QEMU (ten times slower, and
  surprises with Python wheels).
- The database parameters (`aws rds describe-db-instances`) are passed to the chart the way
  `make deploy` does it from `terraform output`: two paths, the same values, and the
  password is read by neither of them (guide 05).
- `rollout status` is `continue-on-error`: readiness refuses as long as the index does not
  exist in RDS (guide 04). The workflow reports the state of the pods, it does not decide on
  your behalf that a deployment failed.

## Run

**1. Set the role ARN in the repository** (once, after the bootstrap):

```bash
ROLE_ARN=$(cd infra/terraform/bootstrap && terraform output -raw github_deploy_role_arn)
gh variable set AWS_DEPLOY_ROLE_ARN --body "$ROLE_ARN"
gh variable list
```

**2. Check that the cluster knows the role** (environment up):

```bash
aws eks list-access-entries --cluster-name llm-testbench-dev --output table
```

Expected: your identity (cluster creator) and the `llm-testbench-github-deploy` role.

**3. Trigger and follow**:

```bash
make deploy-trigger                 # gh workflow run deploy.yml --ref main
gh run watch                        # or: gh run list --workflow=deploy.yml
```

Expected, in the job log: `Assumed role: arn:aws:sts::<account>:assumed-role/
llm-testbench-github-deploy/GitHubActions`, an ECR push with the tag = the first 7 characters
of the SHA, `Release "api" has been upgraded`, then the pods. If the index is not yet in RDS,
the rollout times out and the job stays green with the warning: this is intended.

**4. Read the trace on the AWS side** — that is the whole point of OIDC:

```bash
aws cloudtrail lookup-events --lookup-attribute AttributeKey=EventName,AttributeValue=AssumeRoleWithWebIdentity \
  --max-results 3 --query 'Events[].{time:EventTime,who:Username}' --output table
```

Expected: one line per workflow run, with `GitHubActions` as the session name.
CloudTrail also keeps the token's `sub` in the event detail: you know which repository
and which branch deployed, something a shared key will never tell you.

**5. Deploy a rollback**: rerun the workflow on an earlier commit (`gh workflow run
deploy.yml --ref <sha>`)… and observe that it is refused: the `sub` of a SHA is not that of
`main`. A rollback is done with a `git revert` pushed to `main`, then the workflow. It is a
chosen constraint: we only deploy what is on the branch.

## Pitfalls

- **The cluster's public endpoint stays open** (`public_access_cidrs = ["0.0.0.0/0"]`): GitHub
  runners have no fixed IP, and EKS accepts only a handful of CIDRs. Access is
  authenticated by IAM and logged; it is not an open door, it is a door with a
  badge reader. Truly closing it goes through pull mode (GitOps) or a runner in the VPC — and
  the day that is done, `make deploy` from your workstation must go through the same path.
- **Least privilege on the cluster**: `AmazonEKSEditPolicy` scoped to the `llm-testbench`
  namespace is not enough, because the workflow creates the namespace (a cluster
  resource) and `ExternalSecret`s (a CRD, outside the standard `edit` roles unless aggregated).
  The clean answer: namespace created by Terraform or `cluster-addons`, `Edit` policy on the
  namespace, and an aggregated `ClusterRole` for `external-secrets.io` — three pieces for a
  single-user cluster. Noted, not done.
- **Missing `id-token: write`**: the error says "Credentials could not be loaded" or talks
  about the audience. Check the `permissions` block first.
- **The `sub` must match exactly**: a workflow triggered on another branch, or
  with a GitHub `environment:`, changes the `sub` (`repo:...:environment:dev`). The trust
  policy is the only place that says so.
- **The OIDC provider's thumbprints**: AWS no longer uses them for GitHub (public chain of
  trust), but the Terraform resource requires them. If GitHub changes its intermediate
  certificate, nothing breaks; if the list is empty, the apply fails.
- **One OIDC provider per URL and per account**: a second `terraform apply` from another
  project fails with `EntityAlreadyExists`. You import it (`terraform import ... <arn>`), you
  do not duplicate it.
- **A green `rollout status` does not mean "it works"**: it says the pods are ready.
  `/readyz` and `/sources` (guide 04) say whether the API really responds.

## Interview questions

<details><summary><b>1. How does a CI system authenticate to a cloud without a stored key?</b></summary>

Through identity federation: the CI issues a signed OIDC token that describes the job
(repository, branch, trigger), the cloud has been configured to trust that issuer, and it
exchanges the token for temporary credentials of a role whose trust policy filters on the
token's claims. Nothing is stored; every exchange is logged with the job's identity.
</details>

<details><summary><b>2. What do you put in the trust policy, and why the `sub`?</b></summary>

The audience (`sts.amazonaws.com`) and the `sub`, which encodes repository + ref. Without a
condition on the `sub`, any GitHub repository in the world could assume the role: the OIDC
provider is the same for everyone. It is the most frequent misconfiguration of this mechanism.
</details>

<details><summary><b>3. IAM versus Kubernetes RBAC: who decides what?</b></summary>

IAM decides who can *talk* to the EKS API (`eks:DescribeCluster` to obtain the kubeconfig,
then the IAM-signed token). Access entries, or the old `aws-auth`, bridge the two: they
map an IAM identity to Kubernetes rights (predefined EKS policies or RBAC groups).
After that, Kubernetes RBAC decides on every verb for every resource.
</details>

<details><summary><b>4. Push or pull to deploy to a cluster?</b></summary>

Push (this workflow): the CI pushes a release into the cluster; simple, but the CI needs
network access and rights on the cluster. Pull (GitOps): an operator in the cluster
watches a repository or a registry and reconciles; the cluster exposes nothing, the desired
state is in git, and drift is visible. With a single service and an ephemeral cluster, push;
as soon as there are several environments or a private endpoint, pull.
</details>

<details><summary><b>5. Why is the image built on an arm64 runner?</b></summary>

Because the nodes are Graviton (arm64). An amd64 image does not start (`exec format
error`); a cross-build under QEMU works but takes ten times longer and
runs into Python wheels with no arm64 variant. The native runner removes the problem, and it
is also what you have on an Apple Silicon Mac: a single architecture end to end.
</details>

## What we did not do, and why

- **No GitOps (Argo CD, Flux)**: one more operator on a cluster we destroy every
  evening; revisited in phase 5 with the canary (Argo Rollouts), which really needs it.
- **No GitHub environment with approval**: a single human; the protection would be
  theater. The day a second contributor arrives, `environment: dev` with a required
  reviewer, and the `sub` in the trust policy changes with it (pitfalls).
- **No image signing (cosign) or SBOM**: nothing consumes the signature; to
  do when an admission policy (Kyverno) verifies it. ECR scan on push, on the other hand,
  is active (guide 03).
- **No automatic deployment on push**: the cluster is not always there. When it
  is (phase 5, continuous synthetic traffic), this workflow gains an `on: push` and a
  `paths:` on `src/`, `infra/helm/`, `Dockerfile`.
- **No restriction of the endpoint to an IP**: see the pitfalls, and ADR 009.
