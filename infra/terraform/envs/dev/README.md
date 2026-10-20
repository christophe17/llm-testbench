# `dev` environment — EKS, RDS pgvector, ECR, S3, Secrets Manager

An **ephemeral** environment: `make infra-up` creates it in ~20 minutes, `make infra-down`
destroys it entirely (database included, no snapshot). Nothing should stay up without a
reason. Step-by-step guides: `docs/infra/02` to `06`.

## Estimated cost (eu-west-3, public prices recorded on 2026-09-03, to be checked in Cost Explorer)

| Module | Resource | Up | Down |
|---|---|---|---|
| eks | control plane | ~$0.10/h | 0 |
| eks | 2 × t4g.medium on demand | ~$0.08/h | 0 |
| network | NAT Gateway (`nat_gateway = "single"`) | ~$0.05/h + $0.05/GB | 0 |
| rds | db.t4g.micro + 20 GB gp3 | ~$0.02/h + ~$2.3/month | 0 |
| ecr | images (≤ 10 kept) | ~$0.10/GB/month | same as long as not destroyed |
| secrets | 4 Secrets Manager secrets | ~$1.60/month | 0 after `infra-down` |
| s3 | working bucket | ~$0.02/GB/month | 0 after `infra-down` |
| **Total** | | **~$0.25/h ≈ $6/day** | **~$0** |

A day of testing = ~$6. A forgotten month = ~$180: that is why the budget alert (guide 00)
exists before this environment.
