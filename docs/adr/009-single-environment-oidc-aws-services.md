# ADR 009 — A single ephemeral environment, deployment via OIDC, entry rule for AWS services

- **Date**: 2026-10-19
- **Status**: accepted

## Context

Project resumed after a month-long pause, audit of the brief and the infra in light of the
program (`~/Roadmaps/program`, PD-18: this testbench is the proof for freelance engagements, and
Christophe wants to build up AWS skills without making a bad infra decision for
teaching reasons). Three findings:

1. the brief (§4) planned `dev` and `prod` environments, a legacy of the time when the
   project was a product; a testbench without users has nothing to put into production, and a
   second environment is an idle cost item and Terraform without load;
2. deployment was manual (`make deploy` from the workstation, decision of 2026-09-03), even
   though the CI/CD-on-AWS keyword is at the heart of the positioning and phase 5 (canary,
   rollback) needs a reproducible deployment mechanism;
3. the request "use as many AWS services as possible to learn" had no
   rule: without a rule, we stack (brief §6 forbids it), or we refuse everything.

Added to this is a compromise documented since phase 1: the RDS password went through the
Terraform state to compose the database URL.

## Options considered

**Environments.** (1) `dev` + `prod` as written — faithful to the brief, but `prod` would have neither
traffic nor reason to exist, and would double the running cost. (2) **A single ephemeral `dev`** — the
canary and the shadow of phase 5 are demonstrated within one cluster (two Helm releases, one
routing), not between two environments; if some day an engagement requires a real `prod`, it gets
created then, with its reason.

**Deployment.** (1) Manual from the workstation — simple, not reproducible, no trace. (2)
AWS key in GitHub secrets — never. (3) **GitHub Actions with an OIDC role**, triggered
manually (ephemeral cluster), arm64 runner, build + ECR push + `helm upgrade` — identical to
`make deploy`, no stored secret, traced in CloudTrail. (4) GitOps (Argo CD / Flux) — the
production answer when the endpoint is private; one more operator on a cluster destroyed
every evening, deferred to phase 5 with Argo Rollouts.

**AWS services.** (1) Minimum (EKS, RDS, ECR, S3, Secrets Manager) and nothing else — safe, but
leaves AWS learning outside the testbench. (2) Maximum "to learn" (Lambda, Step
Functions, Kendra, OpenSearch Serverless, SageMaker…) — that is the stacking the brief
forbids, and managed RAG services hide exactly what the testbench measures. (3) **An
entry rule**: an AWS service comes in when it is the natural answer to a block already planned
by the roadmap, or as a measured comparison arm; never as the single path; each
service has an equivalent local implementation behind the same abstraction.

## Decision

Option 2, option 3, option 3.

- **A single `dev` environment, ephemeral.** `CLAUDE.md` §4 corrected; `infra/terraform/README.md`
  no longer mentions `envs/prod`.
- **Deployment via GitHub Actions and OIDC**: OIDC provider and role `llm-testbench-github-deploy`
  in the bootstrap (account identity, stable, free); access entry `AmazonEKSClusterAdminPolicy`
  in `envs/dev`; workflow `deploy.yml` as `workflow_dispatch`, runner `ubuntu-24.04-arm`,
  which reads the database address and its secret's ARN through the RDS API, never through the
  Terraform state. The test CI stays offline and without secrets (ADR 003). Guide 09.
- **Accepted consequence: the cluster's public endpoint stays open** (`public_access_cidrs`
  at `0.0.0.0/0`). GitHub runners have no fixed IP; access is authenticated by IAM and
  logged. Restricting to one IP and the pipeline are mutually exclusive without a runner in the VPC or
  pull mode; we choose the pipeline, and the variable remains for anyone who only deploys from their
  workstation.
- **The database URL is composed in the cluster** by an External Secrets template (engine
  v2, `urlquery`), from the RDS-managed secret; Terraform no longer reads the password.
  The `database-url` secret disappears.
- **Entry rule for AWS services**, written into `CLAUDE.md` §4, with its first
  applications in the phase files: Bedrock Knowledge Bases as comparison arm
  in notebook 4 of phase 3; SQS (two-implementation abstraction, Postgres `SKIP
  LOCKED` locally), ADOT, Karpenter and Cost Anomaly Detection in phase 5; a GPU node group
  on the existing EKS as second measured target of phase 6, if the G quota is granted
  (request to be made right away); Bedrock Guardrails in phase 7 and AgentCore in phase 4,
  optional, decided at the phase plan. Refused even for learning: multi-account and Control
  Tower, Transit Gateway, Kinesis, Glue, EMR, SageMaker as a platform — no load of the
  testbench justifies them.

## Consequences

- The bootstrap goes from five to eight resources and must be applied before `envs/dev` (it
  already was, for the state bucket). A GitHub repository variable (`AWS_DEPLOY_ROLE_ARN`)
  to set once.
- `make deploy` and the workflow do the same thing by two paths (`terraform output` /
  RDS API); both must evolve together. A chart render test with the
  `database.*` values is in `make helm-lint`.
- Phase 5 inherits two obligations: switch `deploy.yml` to `on: push` when the cluster
  runs continuously, and revisit push versus pull (Argo Rollouts for the canary).
- Phase 6 inherits one more column in its table (AWS target versus specialized
  provider) and a quantified target-choice ADR in place of the decoupling ADR.
- To revisit if a contributor or a client enters the repository: GitHub environment with
  approval, least privilege on the cluster (guide 09, pitfalls), return to PRs (ADR 008).
