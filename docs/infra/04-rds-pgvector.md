# Guide 04 — RDS PostgreSQL with pgvector: the managed database, its access, the index

**Duration**: 20 minutes. **Prerequisites**: guide 03 (environment created). **Cost**:
~$0.02/h + ~$2/month of storage, destroyed with the environment. **Code**:
`infra/terraform/envs/dev/rds.tf`, `infra/helm/llm-testbench-api/templates/externalsecret.yaml`
(the database URL, composed in the cluster), `src/llm_testbench/ingest/sql/001_schema.sql`.

---

## The problem

Locally, Postgres is a `StatefulSet` you restart without a second thought. In the cloud, a
database you operate yourself costs sleepless nights: backups, patches, full disk,
failover. RDS sells exactly that. The question becomes: **which instance, which network,
which password, and how does pgvector get in there** — and, for this testbench, how the API
finds the database without a secret ever passing through a file.

## The options

| Option | Verdict |
|---|---|
| **RDS PostgreSQL 16, `db.t4g.micro`, single-AZ** | **Chosen**: the smallest Graviton instance (2 shared vCPUs, 1 GB), enough for 5,000 abstracts and a handful of queries per second; pgvector is available natively. |
| Aurora Serverless v2 | Scales up and down to zero (0.5 ACU minimum ≈ $0.06/h): more expensive than a micro that is on, interesting for an environment left in place with no traffic. Noted for phase 5. |
| Postgres in the cluster (as locally) | Zero RDS cost, but an EBS volume to manage and no managed backup: this is the choice the brief rejects for the cloud. |
| A dedicated vector service | Rejected by the brief (Postgres + pgvector, ADR 007). |

## Guided reading of the real code

**[`rds.tf`](../../infra/terraform/envs/dev/rds.tf)** — the `terraform-aws-modules/rds`
module:

- `engine_version = "16"`, `family = "postgres16"`: the **family** is the parameter
  group's; forgotten or mismatched, the apply fails late with an obscure message.
- `manage_master_user_password = true`: RDS generates the password and stores it in
  Secrets Manager, with rotation possible. Nobody sees it go through a variable.
- `db_subnet_group_name = module.vpc.database_subnet_group_name`: the database lives in the
  `database` subnets, with no route to the Internet (guide 02).
- `vpc_security_group_ids = [aws_security_group.rds.id]` with **a single inbound rule**:
  port 5432 from the EKS nodes' security group. No address, no CIDR: a security group
  identity, which follows the nodes when they change.
- `multi_az = false`, `backup_retention_period = 1`, `skip_final_snapshot = true`,
  `deletion_protection = false`: the four settings you invert in production, deliberately
  accepted here for a throwaway environment. They are explicit so that they get reread.
- `apply_immediately = true`: a parameter change applies right away, not at the next
  maintenance window (which we will never reach).
- `parameters`: `log_min_duration_statement = 1000` — every query longer than one second
  shows up in the logs. The first diagnostic tool for a badly sized HNSW index.
- `performance_insights_enabled = false`, `monitoring_interval = 0`: the two optional cost
  items of RDS monitoring, disabled in dev.

**The database URL** — Terraform does not compose it and never reads the password: it only
outputs the instance address (`rds_address`) and the ARN of the RDS-managed secret
(`rds_master_secret_arn`, `outputs.tf`). It is the chart's `ExternalSecret` (guide 05) that,
inside the cluster, reads `username` and `password` from that secret and composes
`postgresql://user:password@host:5432/testbench`. The password goes neither through the
Terraform state nor through a second secret (ADR 009). Until 2026-10-19, Terraform read it
and wrote it into a `database-url` secret: a documented compromise, now removed. The other
production answer, IAM authentication to the database (`iam_database_authentication_enabled`),
stays under "what we did not do".

**[`001_schema.sql`](../../src/llm_testbench/ingest/sql/001_schema.sql)**: it is the
application, not Terraform, that creates the extension and the tables at startup
(`CREATE EXTENSION IF NOT EXISTS vector`). On RDS, the master user is allowed to create the
extensions on the supported list, pgvector among them.

## Run

**1. Check the instance**:

```bash
aws rds describe-db-instances --db-instance-identifier llm-testbench-dev \
  --query 'DBInstances[0].[DBInstanceStatus,Engine,EngineVersion,DBInstanceClass,PubliclyAccessible,MultiAZ]' --output table
```

Expected: `available`, `postgres`, `16.x`, `db.t4g.micro`, `False`, `False`.

**2. Check that the database is not reachable from your Mac** (that is the expected
result):

```bash
cd infra/terraform/envs/dev && terraform output -raw rds_address ; cd -
nc -z -w 3 <address> 5432 || echo "unreachable from the Internet: correct"
```

**3. Ingest from the cluster.** The index must be built *inside* RDS; the simplest way is an
ephemeral pod with the API image and the pod's secrets:

```bash
kubectl -n llm-testbench run ingest --rm -i --restart=Never \
  --image=$(cd infra/terraform/envs/dev && terraform output -raw ecr_repository_url):$(git rev-parse --short HEAD) \
  --overrides='{"spec":{"containers":[{"name":"ingest","image":"IMAGE","envFrom":[{"secretRef":{"name":"llm-testbench-api-secrets"}}],"command":["python","-m","llm_testbench.ingest.cli","scifact"]}]}}' \
  --image-pull-policy=IfNotPresent
```

(Replace `IMAGE` with the same image as `--image`.) Expected: the ingestion's JSON report —
~5,000 documents, ~5,000 chunks, ~$0.05 of embeddings.

**4. Observe readiness**:

```bash
kubectl -n llm-testbench get pods            # api 1/1 READY
kubectl -n llm-testbench port-forward svc/api 8000:80 &
curl -s localhost:8000/readyz
curl -s localhost:8000/sources | python3 -m json.tool
```

**5. Look at the database from the inside** (from a pod, not from your Mac):

```bash
kubectl -n llm-testbench run psql --rm -it --restart=Never --image=postgres:16 \
  --env="PGURL=$(kubectl -n llm-testbench get secret llm-testbench-api-secrets -o jsonpath='{.data.LLM_TESTBENCH_DATABASE_URL}' | base64 -d)" \
  -- sh -c 'psql "$PGURL" -c "\dx" -c "select index_key, embedding_model, dimensions from indexes" -c "select count(*) from chunks"'
```

Expected: the `vector` extension listed, one index row, ~5,000 chunks.

## Pitfalls

- **The password in the URL must be encoded**: RDS excludes `/`, `@`, `"` and the space
  from its generated passwords, but not `%`, `#`, `?` or `:`. The External Secrets template
  goes through `urlquery`; without it, one URL in three is invalid — and the error does not
  say why.
- **`db.t4g.micro` has CPU credits**: under sustained load (phase 5), it collapses once the
  credits are exhausted. Moving up a size is a variable.
- **The parameter family** must follow the major version: moving to Postgres 17 requires
  `family = "postgres17"`, not just `engine_version`.
- **A `terraform destroy` with `skip_final_snapshot = false`** asks for a snapshot name and
  fails otherwise. In dev, `true`; in production, the opposite, always.
- **HNSW is built on insert**: ingesting 5,000 vectors of 1,536 dimensions takes a minute
  on a micro; at 500,000, you create the index *after* loading (phase 3, experiment
  matrix).
- **The security group references the nodes' group**: if you recreate the EKS cluster
  alone, the rule follows the new group; if you add nodes outside the module (Karpenter),
  check that they carry the same group.

## Interview questions

<details><summary><b>1. RDS or Aurora, when?</b></summary>

RDS is Postgres as is on an instance: predictable, cheaper at small size, a single zone if
you want. Aurora rewrites the storage layer (six-copy replication, distributed reads,
Serverless v2 that follows the load): more expensive at rest, better for a variable load or
a required high availability. For a testbench: RDS; for the dev environment of a team that
forgets to turn it off: Aurora Serverless.
</details>

<details><summary><b>2. How does the application get the password without it being in the code?</b></summary>

RDS generates it in Secrets Manager; External Secrets reads it with the pod's identity and
puts it in a Kubernetes `Secret`; the pod receives it as an environment variable. Nothing is
written by a human, everything is traced by CloudTrail. Rotation changes the value in
Secrets Manager, External Secrets resyncs it, the pod restarts.
</details>

<details><summary><b>3. Why a database with no public access, and how do you administer it then?</b></summary>

A public database is a permanent target for scans. Without public access, you administer
from the VPC: an ephemeral pod (as above), a bastion, or SSM Session Manager with port
forwarding. Kubernetes port-forward to a `psql` pod is the simplest day-to-day tool.
</details>

<details><summary><b>4. pgvector on RDS: what limits?</b></summary>

The extension version follows the one RDS offers (often a few months behind); the HNSW
index fits in memory or the database crawls — instance memory becomes the main sizing
parameter, ahead of CPU. And `CREATE EXTENSION` requires a role with the privilege, which
the master user has.
</details>

## What we did not do, and why

- **No IAM authentication to the database**: elegant (no password at all anymore), but it
  requires a token renewed every 15 minutes on the application side; to be looked at in
  phase 5 with the "the provider is unavailable" runbook.
- **No read replica and no Multi-AZ**: nothing to protect in dev.
- **No RDS Proxy**: useful when hundreds of short connections saturate the database
  (serverless functions); our psycopg pool is enough.
- **No Performance Insights**: a few euros a month for graphs we will not look at before
  phase 5.
