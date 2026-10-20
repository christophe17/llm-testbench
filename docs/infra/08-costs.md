# Guide 08 — Costs: what each module costs, up and down, and how we know

**Duration**: 15 minutes. **Prerequisites**: none for reading; guide 03 for the
checks. **Code**: `infra/terraform/envs/dev/README.md` (table per module),
`Makefile` (`infra-up`, `infra-down`), `config/llm_pricing.toml` (the cost of LLM calls,
which is not infra but weighs just as much).

---

## The problem

A personal cloud account costs nothing as long as it is empty, and a fortune when you
forget one thing in it. Three categories of cost hide behind a "dev
environment": what is billed **by the hour whether it serves or not** (EKS control plane, nodes,
NAT Gateway, RDS instance), what is billed **for storage** (EBS, S3, ECR, snapshots,
logs) and survives an incomplete `destroy`, and what is billed **by usage** (NAT traffic,
LLM calls). This project's positioning — *I quantify what I deploy* — starts
with knowing which of these items are running right now.

## The options for not paying for a sleeping cluster

| Option | Verdict |
|---|---|
| Let it run and "be careful" | No: the NAT and the control plane give no warning. |
| Scale down to zero nodes in the evening (`node_desired_size = 0`) | Saves the nodes (~$0.08/h), not EKS ($0.10/h), nor NAT, nor RDS. Not enough. |
| **Destroy and recreate** (`make infra-down` / `make infra-up`) | **Chosen**: ~20 minutes to create, zero idle cost. The whole environment is code; what must survive (data) can be regenerated or lives in S3. |
| Stop RDS (7 days max) | Possible complement; RDS restarts on its own after 7 days. Useless if we destroy. |

## Guided reading: the cost table

Read [`infra/terraform/envs/dev/README.md`](../../infra/terraform/envs/dev/README.md).
Four columns: the module, the resource, its cost when **up**, its cost when **down** (after
`infra-down`). The order of the running items, from most to least expensive: EKS control
plane, nodes, NAT Gateway, RDS. The items that remain when down: ECR (images, until
destruction), Secrets Manager ($0.40/secret/month, prorated), residual CloudWatch logs.

Total when up: **~$0.25/h, ~$6/day**. Total when down: **~$0**. A forgotten month:
~$180 — that is the scenario the guide 00 alert ($55/month) catches after
nine days, and that `make infra-down` avoids altogether.

**The tags**, set by the `default_tags` block of each module (`Project`, `Environment`,
`ManagedBy`, `Module`), are what makes the cost *per module* readable in Cost Explorer.
Without tags, the bill is a total; with them, a table.

## Run

**1. Activate the cost allocation tags** (once per account; up to 24 h
to appear):

```bash
aws ce update-cost-allocation-tags-status --cost-allocation-tags-status \
  TagKey=Project,Status=Active TagKey=Module,Status=Active TagKey=Environment,Status=Active
```

**2. Read the cost of the last seven days per service**:

```bash
aws ce get-cost-and-usage --time-period Start=$(date -v-7d +%F),End=$(date +%F) \
  --granularity DAILY --metrics UnblendedCost --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[].{day:TimePeriod.Start,cost:Groups[?Metrics.UnblendedCost.Amount>`0.01`].[Keys[0],Metrics.UnblendedCost.Amount]}' --output json
```

**3. Per module, once the tags are active**:

```bash
aws ce get-cost-and-usage --time-period Start=$(date -v-7d +%F),End=$(date +%F) \
  --granularity MONTHLY --metrics UnblendedCost --group-by Type=TAG,Key=Module --output table
```

**4. Check that nothing remains after `make infra-down`**:

```bash
aws eks list-clusters ; aws rds describe-db-instances --query 'DBInstances[].DBInstanceIdentifier'
aws ec2 describe-nat-gateways --filter Name=state,Values=available --query 'NatGateways[].NatGatewayId'
aws ec2 describe-volumes --filter Name=status,Values=available --query 'Volumes[].[VolumeId,Size]'
aws elbv2 describe-load-balancers --query 'LoadBalancers[].LoadBalancerName'
```

Everything must be empty. `available` EBS volumes and load balancers are the two
classic leftovers of a destroyed cluster (created by Kubernetes, unknown to Terraform).

**5. The cost of LLM calls**, for its part, is read in our traces (attribute
`llm_testbench.cost_usd`, notebook 1) and projected with the pricing table:

```bash
uv run python -c "
from llm_testbench.llm.cost import PricingTable; from llm_testbench.llm.types import Usage
p = PricingTable.from_settings(); u = Usage(input_tokens=1000, output_tokens=300)
print({m: round(p.cost_usd(m, u) * 100_000, 2) for m in p.models if p.models[m].output_per_mtok})"
```

Expected: the cost of 100,000 calls per model — the order of magnitude that decides between a
semantic cache, a smaller model, or self-hosting (phase 6).

## Pitfalls

- **Leftovers after destruction**: orphan EBS volumes, load balancers created by a
  `Service type: LoadBalancer`, RDS snapshots if `skip_final_snapshot` was `false`,
  CloudWatch logs. Check (step 4) rather than assume.
- **EKS extended support** (guide 03) multiplies the control plane cost by six without
  changing a line of code.
- **NAT traffic by the gigabyte**: pulling a 2 GB image ten times a day costs
  cents; downloading a 50 GB dataset from a pod costs one euro per
  download. Dataset caches live in the environment's S3 bucket (same
  region: free), not on Hugging Face every time.
- **Cost Explorer lags by 24 h** and the budget alert by up to 8 h: neither of them
  is a real-time measuring instrument. Real time is `terraform show` and
  the EC2 console.
- **Prices change**: the README table carries a date, like the LLM one.

## Interview questions

<details><summary><b>1. How do you estimate the cost of an environment before creating it?</b></summary>

Per module, from the region's price list: resources billed by the hour
(control plane, instances, NAT, database), for storage (volumes, registry, logs) and by
usage (traffic, calls). You separate up/down, note the date of the prices, and
then check in Cost Explorer that reality follows. `terraform plan` gives no
prices; tools like Infracost derive them from the plan, and that is a good next step.
</details>

<details><summary><b>2. What are the classic idle items of an AWS account?</b></summary>

NAT Gateway, EKS control plane, RDS and EC2 instances stopped "for later",
detached EBS volumes, unassociated Elastic IP addresses, load balancers with no targets,
snapshots. All billed without serving.
</details>

<details><summary><b>3. Cost tags: what are they for and what is their limit?</b></summary>

To break the bill down by project, environment, module, team. Their limit: they only
cover tagged resources (some shared services are not tagged) and
only appear in Cost Explorer once activated as cost allocation tags, with
a delay.
</details>

<details><summary><b>4. LLM call cost or infra cost: which dominates?</b></summary>

It depends on volume, and that is the whole point of phase 6: at low volume, the API
dominates and the infra is negligible; at high volume, self-hosted infra (GPU) becomes
cheaper per million tokens. The break-even point is computed with the numbers from both
tables — the API price table and the infra one.
</details>

## What we did not do, and why

- **No Infracost in CI**: the plan is not produced in CI (it stays offline);
  to add the day a pipeline produces plans.
- **No Cost Anomaly Detection**: phase 5, with cost control and the kill switch.
- **No Savings Plans or reserved instances**: they assume continuous usage, the
  opposite of an ephemeral environment.
- **No Spot**: noted in guide 03 for interruption-tolerant workloads.
