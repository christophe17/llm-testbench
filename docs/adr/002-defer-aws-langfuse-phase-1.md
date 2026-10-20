# ADR 002 — AWS cloud and Langfuse deferred to phase 1, bootstrap only in phase 0

- **Date**: 2026-08-26
- **Status**: accepted

## Context

The brief places "Terraform + Helm infra" and Langfuse in phase 0. Yet nothing is deployed
before phase 1 (no API), and nothing calls an LLM before phase 1 (nothing to trace).
The brief also forbids idle cost items. Self-hosted Langfuse v3 drags along
ClickHouse, Redis and object storage — heavy for k3d on a Mac, running empty.

## Options considered

1. **Stand everything up in phase 0** (EKS, RDS, Langfuse) — compliant with the letter of the
   brief, but pays for a cluster and operates an observability stack with no load to observe.
2. **Bootstrap only in phase 0, the rest in phase 1** — the budget alert exists before
   the first euro of cloud spend; the infra arrives when something consumes it.
3. **Zero AWS in phase 0** — also postpones the budget alert, which is precisely the
   protection we want in place before everything else.

## Decision

Option 2. Phase 0: `infra/terraform/bootstrap/` module only (encrypted/versioned S3 state
bucket with native S3 locking — no DynamoDB, Terraform ≥ 1.10 — and a monthly
budget of 55 USD ≈ €50 with alerts at 80%/100% actual + 100% forecast). The bootstrap
state stays local (it creates the state bucket: chicken and egg). Langfuse is installed
in phase 1 with the first LLM call. Local dev (k3d + Postgres/pgvector), on the other hand,
is indeed delivered in phase 0: the loaders and CI do not depend on it, but phase 1 will
consume it from its very first day.

## Consequences

Phase 0 cloud cost: ~€0/month. Phase 1 will have to deliver: network + EKS + ECR + RDS
pgvector (Terraform, bootstrap S3 backend), a GitHub Actions OIDC role if CI is to
deploy, and the call between full Langfuse v3 and a lightweight local alternative. To revisit
if phase 1 slips: the budget alert, for its part, is already in place.
