# Terraform infra

Two modules, two lifecycles.

| Module | Contents | State | Lifecycle |
|---|---|---|---|
| `bootstrap/` | S3 state bucket (encrypted, versioned, native locking), budget alert, GitHub OIDC provider and deployment role | **local** (it creates the state bucket, it cannot store its own there) | applied once per account (guides 00 and 09) |
| `envs/dev` | VPC, EKS (Pod Identity, access entries), RDS pgvector, ECR, S3, Secrets Manager, roles | S3, bootstrap bucket | **ephemeral**: `make infra-up` in the morning, `make infra-down` in the evening (guides 02 to 06, costs in guide 08) |

There is no `prod` environment: the testbench has no users, a second environment would be an
idle cost item (ADR 009).

## Running the bootstrap (once)

Prerequisites: AWS account created, credentials configured (`aws configure` or SSO), Terraform ≥ 1.10.

```bash
export TF_VAR_alert_email="you@example.com"
make bootstrap-plan     # Plan: 8 to add
make bootstrap-apply
```

If the bootstrap's local state is lost, `terraform import` recovers its eight resources in a
few minutes (identifiers: bucket name, `<account>:llm-testbench-monthly`, OIDC provider ARN,
role name).

## The dev environment

```bash
make infra-init         # bootstrap S3 backend
make infra-plan
make infra-up           # ~20 minutes, then kubeconfig
make cluster-addons     # External Secrets + ClusterSecretStore
make deploy             # or: make deploy-trigger (GitHub Actions, guide 09)
make infra-down         # in the evening
```

## Estimated monthly cost of the bootstrap

| Resource | Cost |
|---|---|
| S3 state bucket (a few KB) | ~€0 |
| AWS Budgets (first 2 budgets) | €0 |
| OIDC provider and IAM role | €0 |
| **Total** | **~€0/month** |

The dev environment: `envs/dev/README.md` (~$0.25/h when up, ~$0 when down).
