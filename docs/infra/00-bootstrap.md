# Guide 00 — AWS bootstrap: remote state and the budget alert before the first euro

**Duration**: 15 minutes. **Prerequisites**: AWS account, AWS CLI configured, Terraform ≥ 1.10.
**Cost**: ~€0/month. **Code**: `infra/terraform/bootstrap/` (`main.tf`, `github.tf`, `variables.tf`, `outputs.tf`).

This guide runs once per account. Everything that follows in phase 1 (network, EKS, RDS)
stores its state in the bucket created here and lives under the budget alert created here.

---

## The problem

Two chicken-and-egg problems, to settle before any other cloud resource.

**1. Terraform state needs somewhere to live.** Terraform keeps the mapping between the code
and the real resources in a state file. Locally, that file is a single point of failure: a
lost disk and Terraform no longer knows what it created; two concurrent `apply` runs and the
state is corrupted. So it needs remote storage that is encrypted, versioned and lockable. But
that storage is itself a cloud resource, which something has to create.

**2. The budget alert must exist before the first billed resource.** The brief forbids idle
cost items. And idle items are silent by nature: a forgotten NAT Gateway costs ~€35/month
without ever announcing itself, an EKS control plane ~€70/month. Without an alert, you
discover the drift on the following month's bill.

## The options

**For the state.**

| Option | Verdict |
|---|---|
| Local file | Rejected: single point of failure, no lock, no history. Accepted *only* for this very module (see below). |
| S3 + DynamoDB table for the lock | The classic answer until 2024. Two services to manage for one lock. Still in most tutorials. |
| **S3 with native locking** (`use_lockfile`, Terraform ≥ 1.10) | **Chosen.** The lock is a `.tflock` object written conditionally in the bucket itself. A single service. |
| HCP Terraform (formerly Terraform Cloud) | Rejected: dependency on a SaaS for a project that wants to show it knows how to operate. |

**For the alert.**

| Option | Verdict |
|---|---|
| **AWS Budgets** | **Chosen.** Free for the first two budgets, thresholds on actual and forecasted spend, email with no infrastructure. |
| CloudWatch alarm on the billing metric | Metric only in `us-east-1`, to be enabled by hand in the console, no forecast. |
| Cost Anomaly Detection | Complementary (statistical detection, free), not a cap. Candidate for phase 5. |

## Guided reading of the real code

Open [`infra/terraform/bootstrap/main.tf`](../../infra/terraform/bootstrap/main.tf).

**The `terraform` block** sets `required_version = ">= 1.10"`. This is not an affectation:
native S3 locking does not exist before that. The AWS provider is pinned to `~> 5.60` (any
5.x from 5.60 on, never 6.x): a major provider upgrade is decided, not caught.

**The `provider` block** carries `default_tags`. Every resource created by this module
inherits `Project`, `ManagedBy`, `Module`. This is what will later make a *per-module* cost
possible in Cost Explorer: without tags, the bill is an undifferentiated total.

**`data "aws_caller_identity"`** reads the current account ID. It is used in the bucket
name: S3 bucket names are unique *worldwide*, not per account. Suffixing with the account ID
avoids colliding with someone else's `llm-testbench-tfstate`.

**The bucket** has a `lifecycle { prevent_destroy = true }`. Terraform will refuse to destroy
it, even on an explicit `terraform destroy`. This is intended: this bucket will hold the state
of everything else, and its accidental destruction would be the worst possible incident of
the project.

**Three ancillary resources** configure the bucket. Since provider 4.x, these settings are
separate resources, no longer bucket arguments:

- `aws_s3_bucket_versioning`: every state write keeps the previous version. A failed
  `apply` is repaired by restoring the version before it.
- `aws_s3_bucket_server_side_encryption_configuration`: `aws:kms` encryption with the
  AWS-managed key (`aws/s3`). Encrypted at rest without creating a key, so without the
  monthly cost of a custom key. `bucket_key_enabled = true` reduces the number of billed KMS
  calls. Terraform state deserves this care: one day it will contain the RDS password in
  plain text.
- `aws_s3_bucket_public_access_block`: the four locks against public exposure. A public
  state bucket is a secrets leak.

**The budget** is in USD: AWS Budgets does not know the euro (USD 55 ≈ €50). The
`dynamic "notification"` block unrolls three alerts from a list: 80% and 100% of **actual**,
100% of **forecasted**. The forecast is the most useful: AWS extrapolates the month's
consumption and warns days before the actual spend breaks through the cap.

**[`variables.tf`](../../infra/terraform/bootstrap/variables.tf)**: region, cap, and the
alert email address, the only variable without a default. **[`outputs.tf`](../../infra/terraform/bootstrap/outputs.tf)**:
the bucket name, a `backend "s3"` block ready to paste into the environment modules, with
`use_lockfile = true`, and the ARN of the deployment role.

**[`github.tf`](../../infra/terraform/bootstrap/github.tf)**: GitHub's OIDC provider and the
role the deployment workflow assumes, read line by line in guide 09. They live here, and not
in `envs/dev`, because this is an account identity: stable, free, and it must survive the
evening `make infra-down`.

## Run

**1. Check identity and tooling.**

```bash
aws sts get-caller-identity
terraform version
```

Expected: your account ID and your user's ARN; Terraform ≥ 1.10. If `get-caller-identity`
fails, nothing else will work: fix `aws configure` first.

**2. Provide the alert address without writing it to a file.**

```bash
export TF_VAR_alert_email="you@example.com"
```

Terraform reads any `TF_VAR_<name>` variable from the environment. This avoids a
`terraform.tfvars` file containing a personal address in a public repository (`*.tfvars` is
now ignored by git, belt and braces). Without this export, `terraform apply` will ask you for
the value interactively: that works too.

**3. Initialize and plan.**

```bash
make bootstrap-plan
```

`terraform init` downloads the AWS provider and prints `Terraform has been successfully
initialized!`. The plan must end with:

```
Plan: 8 to add, 0 to change, 0 to destroy.
```

Eight resources: the bucket, its versioning, its encryption, its public access block, the
budget, then the GitHub OIDC provider, the deployment role and its policy (guide 09). If the
number differs, stop and read the plan.

**4. Apply.**

```bash
make bootstrap-apply
```

Answer `yes`. At the end of the run, three outputs: `tfstate_bucket`, `backend_example` and
`github_deploy_role_arn` (to set in the GitHub repository, guide 09). Note the bucket name:
`llm-testbench-tfstate-<account ID>`.

**5. Check what was created.** Do not take Terraform's word for it, query AWS.

```bash
cd infra/terraform/bootstrap
BUCKET=$(terraform output -raw tfstate_bucket)
aws s3api get-bucket-versioning --bucket "$BUCKET"
aws s3api get-bucket-encryption --bucket "$BUCKET"
aws s3api get-public-access-block --bucket "$BUCKET"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
aws budgets describe-budgets --account-id "$ACCOUNT" \
  --query 'Budgets[].[BudgetName,BudgetLimit.Amount,BudgetLimit.Unit]' --output table
aws budgets describe-notifications-for-budget --account-id "$ACCOUNT" \
  --budget-name llm-testbench-monthly --output table
```

Expected, in order: `"Status": "Enabled"`; `SSEAlgorithm: aws:kms` and
`BucketKeyEnabled: true`; four `true`; a `llm-testbench-monthly` budget at `55 USD`; three
notifications (`ACTUAL 80`, `ACTUAL 100`, `FORECASTED 100`).

**6. Look at where this module's state lives.**

```bash
ls infra/terraform/bootstrap/terraform.tfstate
git check-ignore infra/terraform/bootstrap/terraform.tfstate
```

It is **local**, and git ignores it. This is the deliberate exception: this module creates
the state bucket, it cannot store its own state there. It contains only eight stable
resources. If it is lost, `terraform import` recovers them in a few minutes (the IDs are the
bucket name, `<account>:llm-testbench-monthly` for the budget, the OIDC provider's ARN and
the role name).

**7. Tell me it is done**, with the bucket name. The `envs/dev` modules need it for their
`backend` block.

## Pitfalls

- **The forecast alert is silent at first.** AWS needs about five weeks of consumption
  history to produce a forecast. On a new account, only the actual-spend alerts work the
  first month.
- **A budget is not a circuit breaker.** AWS Budgets refreshes its data up to three times a
  day: up to eight hours can pass between the drift and the email. The real kill switch on
  cost drift is a phase 5 deliverable, not this guide's.
- **`prevent_destroy` also blocks deliberate cleanup.** To actually delete the bucket one
  day: remove the `lifecycle` block, empty the bucket *including all versions* (a versioned
  bucket that is not emptied refuses deletion), then `destroy`.
- **The `aws/s3` key is not your own key.** Encrypted, yes; but no controlled rotation, no
  key policy, no cross-account sharing. Enough for a personal Terraform state; in a company,
  you move to a customer-managed key.
- **Your credentials are those of an IAM user with long-lived keys.** Acceptable on a
  personal account. The production answer is IAM Identity Center (SSO, temporary
  credentials) for humans and OIDC for CI — the latter is done, guide 09.
- **The `.terraform.lock.hcl` file is ignored by git** since phase 0. For this module, it
  makes no difference; for the environment modules, we will version it with the hashes of
  both platforms (`darwin_arm64` for you, `linux_amd64` for a future CI), otherwise two
  machines can resolve two different provider versions.
- **The bucket is in `eu-west-3`, the budget is global.** AWS Budgets has no region: do not
  look for the budget in the Paris console, it is in "Billing and Cost Management".
- **Another state bucket exists on this account**, created by another project. This module
  does not touch it and creates its own: one state per project, never shared.

## Interview questions

<details><summary><b>1. Why remote state, and what happens without a lock?</b></summary>

State is Terraform's only memory: lose it, and Terraform will recreate everything as
duplicates. Without a lock, two simultaneous `apply` runs read the same state, each writes
its own, and the second overwrites in the state the resources created by the first without
destroying them in the cloud: orphaned resources, billed, invisible to Terraform.
</details>

<details><summary><b>2. S3 + DynamoDB or native S3 locking: what is the difference?</b></summary>

Same guarantee (mutual exclusion of operations), different mechanism: DynamoDB uses a table
with a conditional write; native locking uses S3's conditional write (`If-None-Match`) on a
`.tflock` object. Native locking requires Terraform ≥ 1.10 and removes one service to manage.
Both can coexist during a migration.
</details>

<details><summary><b>3. What does versioning the state bucket concretely buy you?</b></summary>

Rolling back after an `apply` that corrupted the state, and recovering the state from before
an unfortunate `terraform state rm`. It is also an audit trail: who changed what, when.
</details>

<details><summary><b>4. Why encrypt the state, and SSE-S3 or SSE-KMS?</b></summary>

The state contains sensitive values in plain text: database passwords, tokens, private
addresses. SSE-S3 (AES-256 managed by S3) meets basic compliance; SSE-KMS adds CloudTrail
traceability of key access and, with a custom key, control over its policy. We took SSE-KMS
with the AWS key: the trail without the cost.
</details>

<details><summary><b>5. How do you handle the bootstrap chicken-and-egg problem?</b></summary>

Three known answers: deliberate local state for the bootstrap module only (our choice, with
`import` as the recovery plan); manual creation of the bucket followed by an import; or a
first `apply` locally followed by migrating the state into the bucket it just created
(`terraform init -migrate-state`). The third is elegant but creates a circular dependency
that has to be explained at every resumption.
</details>

<details><summary><b>6. Is a budget alert enough to keep costs under control?</b></summary>

No: it detects, it does not prevent, and with a delay of several hours. Control comes from
the architecture (nothing idle: `make infra-down`), tags for attribution, anomaly detection
for surprises, and an automatic shutdown mechanism for fast drifts. The budget is the safety
net, not the seat belt.
</details>

## What we did not do, and why

- **No DynamoDB**: native locking is enough and it is one service fewer.
- **OIDC for CI has been here since 2026-10-19** (`github.tf`, ADR 009): the *test* CI stays
  offline and secret-free (ADR 003); only the deployment workflow, triggered by hand, assumes
  the role (guide 09).
- **No custom KMS key**: no need for key policy control on a personal account.
- **No Cost Anomaly Detection**: complementary, to be added in phase 5 with the rest of cost
  control.
- **No IAM Identity Center**: personal account, a single human; noted as the production
  answer in guide 03.

## Cost

| Resource | Monthly cost |
|---|---|
| S3 state bucket (a few KB, versioned) | ~€0 |
| KMS calls on the `aws/s3` key | ~€0 (cents at worst) |
| AWS Budgets (first two budgets) | €0 |
| GitHub OIDC provider, IAM role | €0 |
| **Total** | **~€0** |
