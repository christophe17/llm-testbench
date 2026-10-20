# Infrastructure guides

The guides in this folder explain the testbench's infra with the same teaching contract as
the notebooks: the problem, the options, guided reading of the **real code** (HCL, YAML,
Makefile), a step-by-step run with the expected outputs and the checks to perform, the
pitfalls, the interview questions, and what we did not do. They are run from the CLI, by
hand: they need credentials and a cluster, which an offline CI does not have.

Calibration: Kubernetes and Terraform vocabulary is assumed; every AWS choice, every
trade-off and every pitfall is spelled out. The rule for admitting an AWS service into the
testbench is in `CLAUDE.md` §4 (ADR 009).

| # | Guide | What we build | Cost when on |
|---|---|---|---|
| 00 | [Bootstrap](00-bootstrap.md) | Terraform state bucket, budget alert, GitHub OIDC role | ~€0/month |
| 01 | [Local dev k3d](01-local-dev-k3d.md) | local cluster, Postgres/pgvector, Tilt | €0 |
| 02 | [VPC network](02-network-vpc.md) | subnets, routing, NAT or endpoints | ~$0.05/h + traffic |
| 03 | [EKS](03-eks.md) | control plane, Graviton nodes, access, pod identities | ~$0.18/h |
| 04 | [RDS pgvector](04-rds-pgvector.md) | managed database, extension, access from the cluster | ~$0.02/h |
| 05 | [Secrets](05-secrets.md) | Secrets Manager, External Secrets, database URL composed in the cluster | ~$1.60/month |
| 06 | [API Helm chart](06-helm-chart-api.md) | probes, HPA, PDB, resources | €0 |
| 07 | [Observability](07-observability.md) | Langfuse, OTel collector | €0 locally |
| 08 | [Costs](08-costs.md) | cost per module, `make infra-up` / `make infra-down` | — |
| 09 | [Deployment via GitHub Actions](09-github-oidc-deployment.md) | OIDC role, arm64 build, ECR, Helm, keyless | €0 |

Total for the `dev` environment when on: ~$0.25/h, ~$6/day; off: ~$0 (guide 08).
