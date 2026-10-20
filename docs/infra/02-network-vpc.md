# Guide 02 — The network: VPC, subnets, NAT or no NAT

**Duration**: 20 minutes. **Prerequisites**: guide 00 applied (state bucket). **Cost**: the
plan creates nothing; the NAT Gateway, if we keep it, will cost ~$0.05/h once applied
(guide 03). **Code**: `infra/terraform/envs/dev/network.tf`, `locals.tf`, `variables.tf`.

---

## The problem

A cluster needs three things the network must keep apart: **public** addresses for what
receives traffic from the Internet (load balancers), **private** addresses for what must
never be reachable from outside (nodes, pods), and an even more closed-off corner for the
database. And the private nodes still need to **get out**: pull images, call the LLM
providers' APIs, reach the control plane.

That last point is what costs money: egress from a private subnet goes through a NAT
Gateway, billed by the hour and by the gigabyte, **whether it is used or not**. It is the
number one idle cost item on personal AWS accounts.

## The options

| Option | Cost | Verdict |
|---|---|---|
| One NAT Gateway per AZ | ~$0.10/h | The production answer (no cross-AZ dependency). Too expensive for an ephemeral dev environment. |
| **A single NAT Gateway** (`nat_gateway = "single"`) | ~$0.05/h + $0.05/GB | **Default**: production topology (private nodes), acceptable cost for a few hours. |
| **No NAT, nodes in public subnets** (`nat_gateway = "none"`) | 0 | Nodes with a public IP but a security group closed to inbound traffic. "Dev" topology, zero idle cost. |
| VPC endpoints (S3, ECR, Secrets Manager…) | ~$0.01/h each | Reduces NAT traffic, does not eliminate it (the LLM APIs are on the Internet). Postponed. |

The choice is a variable: you can do both and compare in Cost Explorer.

## Guided reading of the real code

**[`locals.tf`](../../infra/terraform/envs/dev/locals.tf)** — two availability zones (the
minimum for EKS, which refuses a single AZ), and three families of subnets computed with
`cidrsubnet` from the `/16`: public in `10.42.0-1.0/24`, private in `10.42.10-11.0/24`,
database in `10.42.20-21.0/24`. Computing rather than hard-coding: changing the CIDR only
requires touching one variable.

**[`network.tf`](../../infra/terraform/envs/dev/network.tf)** — the
`terraform-aws-modules/vpc` module (the most widely used in the ecosystem, ~240 variables;
we use twelve):

- `create_database_subnet_group = true`: the subnet group RDS will require in guide 04,
  created here because it belongs to the network.
- `enable_dns_hostnames`: without it, private endpoints (RDS, control plane) have no
  resolvable name inside the VPC.
- `enable_nat_gateway = (var.nat_gateway == "single")` and `single_nat_gateway = true`: a
  single gateway shared by both AZs (by default the module would create one per AZ).
- `map_public_ip_on_launch`: in no-NAT mode, nodes get a public IP at startup, otherwise
  they would never get out.
- **The `kubernetes.io/role/elb` and `internal-elb` tags**: this is how Kubernetes
  controllers (Service of type LoadBalancer, AWS Load Balancer Controller) know which
  subnets to place a load balancer in. Without these tags, a `Service
  type: LoadBalancer` stays `<pending>` without explaining why.

**[`eks.tf`](../../infra/terraform/envs/dev/eks.tf)**, only two lines for this guide:
`subnet_ids` picks the public or private subnets for the nodes depending on the variable,
and `control_plane_subnet_ids` places the control plane's interfaces in private subnets in
every case.

## Run

**1. Initialize with the bootstrap backend.**

```bash
make infra-init
```

The Makefile passes `-backend-config="bucket=llm-testbench-tfstate-<account>"`: the bucket
name depends on the account, it is never written in the code. Expected: download of the
modules (vpc, eks, rds) and providers, then `Terraform has been successfully
initialized!`. The `.terraform.lock.hcl` file is versioned with the hashes of three
platforms (Mac arm64, Linux amd64 and arm64): a Linux CI would resolve the same provider
versions as you.

**2. Plan the whole environment**, but read only the network for now:

```bash
make infra-plan 2>&1 | tee /tmp/plan.txt
grep -E "^  # module.vpc" /tmp/plan.txt
```

Expected: one VPC, 6 subnets, an Internet gateway, route tables, an Elastic IP and a NAT
Gateway (in `single` mode), a database subnet group. Count: about 25 resources for the
network alone, out of ~70 for the environment.

**3. Try the other mode** without creating anything:

```bash
cd infra/terraform/envs/dev && terraform plan -var nat_gateway=none | grep -E "nat_gateway|eip" ; cd -
```

No more NAT or EIP in the plan. Choose, then record your choice in `terraform.tfvars`
(ignored by git) if you deviate from the default.

## Pitfalls

- **The NAT Gateway is billed even without traffic**: ~$35/month if forgotten. This is the
  reason for `make infra-down` and for the guide 00 alert.
- **Public nodes are not "open"**: a public IP and a security group that allows nothing
  inbound is reachable by no one. The difference from private is the margin for error (one
  more rule and it is open), not the default exposure.
- **`0.0.0.0/0` on the control plane's public endpoint** (`public_access_cidrs`): the
  project default for simplicity; in practice, put your IP as a `/32`. The Kubernetes API
  remains authenticated, but exposing the authentication port to the whole world is never
  free.
- **The `/16` is generous on purpose**: EKS pods each consume one VPC IP (VPC CNI). One
  `/24` per private subnet is ~250 pods per AZ: enough here, tight in production.
- **Subnet tags are invisible until the day they are missing**: a LoadBalancer stuck in
  `<pending>` or an obscure controller error. They are in the code, not in your memory.

## Interview questions

<details><summary><b>1. Public, private, database: why three families?</b></summary>

Three routing policies: public subnets have a route to the Internet gateway (they receive),
private ones a route to the NAT (they get out without receiving), the database one no route
to the outside (it does neither). The security group protects the instance; the subnet
protects against a security group mistake.
</details>

<details><summary><b>2. How do you reduce the egress cost of a private cluster?</b></summary>

VPC endpoints for AWS services (S3 as a gateway endpoint, free; ECR, Secrets Manager,
CloudWatch as interface endpoints, ~$0.01/h each) so that this traffic no longer goes
through the NAT; a single NAT in dev; and monitor NAT traffic per gigabyte, often dominated
by image pulls (hence the ECR endpoint first).
</details>

<details><summary><b>3. Why does EKS require two AZs?</b></summary>

The managed control plane is deployed by AWS in high availability across several AZs; it
needs subnets in at least two. Your nodes, on the other hand, can stay in a single AZ if you
accept the risk.
</details>

<details><summary><b>4. Which address does a pod's outbound traffic use?</b></summary>

In private mode: the NAT Gateway's IP (a single address for the whole cluster, handy for a
provider's allowlist). In public mode without NAT: its node's public IP, which changes every
time the node is replaced — impossible to allowlist.
</details>

## What we did not do, and why

- **No VPC endpoints**: a real gain only with sustained AWS traffic; to be measured in
  phase 5 with the traffic generator.
- **No flow logs**: useful for network auditing, out of scope in an ephemeral dev
  environment.
- **No IPv6**: no need, and dual-stack VPC CNI adds cases to handle.
- **No NAT per AZ**: high availability for egress makes no sense for an environment we
  destroy every evening.
