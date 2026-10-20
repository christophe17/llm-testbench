# Guide 05 — Secrets: Secrets Manager, External Secrets, pod identities

**Duration**: 15 minutes. **Prerequisites**: guide 03 (cluster and add-ons). **Cost**:
~$0.40/month per secret (three keys, plus the RDS-managed secret), destroyed with the
environment. **Code**:
`infra/terraform/envs/dev/secrets.tf`, `iam.tf`, `infra/k8s/dev/cluster-secret-store.yaml`,
`infra/helm/llm-testbench-api/templates/externalsecret.yaml`.

---

## The problem

An LLM API key gives access to an account billed by usage: it is a means of payment.
It must reach the pod without going through git, an image, a Helm values file, or a
colleague's terminal. And when it changes (rotation, leak), the change must propagate
without a manual redeploy.

## The options

| Option | Verdict |
|---|---|
| Kubernetes `Secret` created by hand | What we do locally (`make k8s-secrets`): simple, but the source of truth sits on a workstation, and nothing resyncs it. |
| Encrypted secret in git (SOPS, Sealed Secrets) | Good for GitOps; but API keys change outside git and the source of truth would be duplicated. |
| **Secrets Manager + External Secrets Operator** | **Chosen**: the source of truth is in Secrets Manager (audited, rotatable), the operator copies it into a Kubernetes `Secret` and resyncs it; authentication goes through the pod identity. |
| SSM Parameter Store (SecureString) | Free in the standard tier, with no built-in rotation or rich versioning. Fine for configuration, less so for means of payment. |
| Secrets Store CSI Driver | Mounts secrets as files, without a Kubernetes `Secret`; more moving parts for a limited gain here. |

## Guided reading of the real code

**[`secrets.tf`](../../infra/terraform/envs/dev/secrets.tf)** — three key secrets
(`llm-testbench/dev/anthropic-api-key`, `openai-api-key`, `openrouter-api-key`), and nothing
else: the database URL is not a Terraform secret (see the template below). Two
details that matter:

- `recovery_window_in_days = 0`: Secrets Manager normally keeps a deleted secret for
  30 days (and the name stays locked). Zero, so that an `infra-down` followed by an `infra-up`
  does not hit "secret already scheduled for deletion".
- the initial version is `REPLACE_ME` with `ignore_changes = [secret_string]`:
  Terraform creates the secret but **never manages its value**. You set it by hand;
  Terraform will never overwrite it, and it will never enter the state.

**[`iam.tf`](../../infra/terraform/envs/dev/iam.tf)** — the `external_secrets` role: read
and describe the secrets under the `llm-testbench/dev/*` prefix and the RDS-managed secret
(`module.rds.db_instance_master_user_secret_arn`), nothing else; associated through
Pod Identity with the `external-secrets` ServiceAccount in the namespace of the same name
(created by the operator's chart).

**[`cluster-secret-store.yaml`](../../infra/k8s/dev/cluster-secret-store.yaml)** — the
`ClusterSecretStore` tells the operator *where* to read (Secrets Manager, region) and *how*
to authenticate: nothing declared, so the SDK's default credential chain, which
finds the pod identity. No key, no role ARN: the association is made by
Terraform.

**[`externalsecret.yaml`](../../infra/helm/llm-testbench-api/templates/externalsecret.yaml)**
— in the API's namespace, one `ExternalSecret` per deployment: each `data` entry maps
an environment variable to a Secrets Manager key; the operator
builds the `llm-testbench-api-secrets` `Secret` that the Deployment consumes, and
refreshes it every hour (`refreshInterval`). When `database.masterSecretArn` is
set (by `make deploy` or the workflow, from the Terraform outputs / the RDS API),
two extra `data` entries read `username` and `password` from the RDS-managed secret
(`remoteRef.property`), and a `target.template` block (engine v2) composes
`LLM_TESTBENCH_DATABASE_URL` in the cluster, with the password encoded by `urlquery`. Read the
braces on two levels: `{{ .Values... }}` is rendered by Helm, `{{ .db_password }}` is
left as is for the operator. This is the production answer to the earlier compromise
(ADR 009): the password leaves Secrets Manager only for the Kubernetes `Secret`.

## Run

**1. Set the real values** (once per environment, from your workstation):

```bash
aws secretsmanager put-secret-value --secret-id llm-testbench/dev/anthropic-api-key --secret-string "$ANTHROPIC_API_KEY"
aws secretsmanager put-secret-value --secret-id llm-testbench/dev/openai-api-key --secret-string "$OPENAI_API_KEY"
aws secretsmanager put-secret-value --secret-id llm-testbench/dev/openrouter-api-key --secret-string "$OPENROUTER_API_KEY"
```

Load `.env` first (`set -a; source .env; set +a`) so you do not paste a key into
the shell history. The database URL, for its part, is composed by the operator from the
RDS-managed secret: nothing to set.

**2. Check the synchronization**:

```bash
kubectl -n llm-testbench get externalsecret api        # STATUS SecretSynced, READY True
kubectl -n llm-testbench get secret llm-testbench-api-secrets -o jsonpath='{.data}' | python3 -c "import sys,json; print(list(json.load(sys.stdin)))"
```

Expected: the four keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`,
`LLM_TESTBENCH_DATABASE_URL`). If `READY False`: `kubectl describe externalsecret api`
gives the reason (access denied → Pod Identity association, prefix or ARN in the IAM
policy; secret not found → name; template error → a missing `data` key).

Check the composed URL **without displaying the password**:

```bash
kubectl -n llm-testbench get secret llm-testbench-api-secrets -o jsonpath='{.data.LLM_TESTBENCH_DATABASE_URL}' \
  | base64 -d | sed -E 's#//[^:]+:[^@]+@#//<user>:<password>@#'
```

Expected: `postgresql://<user>:<password>@<RDS address>:5432/testbench`. If the pod does not
connect although the address is right, it is the encoding: compare the length of the
password in Secrets Manager and in the `Secret` — `urlquery` lengthens reserved
characters (`%23` for `#`).

**3. Prove that the pod has no AWS key**:

```bash
kubectl -n llm-testbench exec deploy/api -- env | grep -c AWS_ACCESS_KEY_ID || echo "no static key"
kubectl -n external-secrets exec deploy/external-secrets -- env | grep AWS_CONTAINER_CREDENTIAL_FULL_URI
```

**4. Rotate a key**: change the value in Secrets Manager
(`put-secret-value`), wait for the `refreshInterval` (or annotate the `ExternalSecret` with
`force-sync=$(date +%s)`), then restart the API (`kubectl rollout restart deploy/api`):
a process does not reread its environment variables.

## Pitfalls

- **Deletion with a recovery window** locks the name for 30 days: without
  `recovery_window_in_days = 0`, the second `infra-up` fails.
- **`ignore_changes` cuts both ways**: Terraform will not restore a value
  erased by mistake either. The backup of the value is you.
- **The synced `Secret` is not reread by a running pod**: after a rotation,
  restart. A tool like Reloader can automate that restart on a `Secret`
  change; to add if rotations become frequent.
- **The IAM prefix is strict**: a secret named outside `llm-testbench/dev/` is
  invisible to the operator, by construction. It is a protection, not a bug.
- **A `ClusterSecretStore` is cluster-wide**: any namespace can create an
  `ExternalSecret` against it. In a shared cluster, one `SecretStore` per namespace and
  separate roles.
- **The managed RDS secret is not in the format the application expects** (JSON
  `{username, password}`): hence the `ExternalSecret` template, which reads two properties and
  composes the URL. **`mergePolicy` defaults to `Replace`**: only the keys written by the
  template enter the `Secret`, so the template restates every API key — forgetting one
  makes it vanish from the pod without any error message.

## Interview questions

<details><summary><b>1. Where is a secret's source of truth, and why not in the cluster?</b></summary>

In a secrets manager (Secrets Manager): encrypted with KMS, versioned, audited
by CloudTrail, with rotation. A Kubernetes `Secret` is base64-encoded in etcd
(encrypted at rest only if that was configured, which `create_kms_key` does here) and
readable by anyone with `get secrets` in the namespace. The Kubernetes `Secret` is a
working copy, not the source of truth.
</details>

<details><summary><b>2. How does the operator authenticate to AWS?</b></summary>

Through the pod identity: its ServiceAccount is associated with an IAM role whose policy is
limited to the project's secret prefix. No access key. The AWS SDK in the pod finds
the temporary credentials via the Pod Identity agent, exactly like the API does for Bedrock.
</details>

<details><summary><b>3. Secrets Manager or Parameter Store?</b></summary>

Standard Parameter Store is free and enough for configuration, including
encrypted configuration (SecureString). Secrets Manager costs $0.40/secret/month and brings
built-in rotation (RDS, Lambda), rich versioning and replication. Simple rule: a means of
payment or a password that rotates → Secrets Manager; a setting → Parameter Store.
</details>

<details><summary><b>4. What happens when a key leaks?</b></summary>

Revoke it at the provider, set the new value in Secrets Manager, force the
sync, restart the pods; then read CloudTrail to find out who read the secret
and when. Phase 5 will add the cost kill switch: a leaked key shows up first
on the bill.
</details>

## What we did not do, and why

- **No automatic rotation of LLM keys**: providers do not expose a rotation
  API; rotation is manual by construction.
- **No Reloader**: a rare rotation is handled with a `rollout restart`.
- **No IAM authentication to the database** (guide 04): the password still exists,
  but it leaves Secrets Manager only for the Kubernetes `Secret`, composed in the
  cluster. The template replaced the Terraform compromise on 2026-10-19 (ADR 009).
- **No per-namespace SecretStore**: a single tenant on this cluster.
