# Network. The idle cost item to watch is the NAT Gateway (~$0.05/h + traffic):
# `nat_gateway = "none"` puts the nodes in public subnets (public IP, security group
# closed to ingress) and removes that cost — acceptable for an ephemeral dev.

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.7"

  name = var.name
  cidr = var.vpc_cidr
  azs  = local.azs

  public_subnets   = local.public_subnets
  private_subnets  = local.private_subnets
  database_subnets = local.database_subnets

  create_database_subnet_group = true
  enable_dns_hostnames         = true
  enable_dns_support           = true

  enable_nat_gateway = var.nat_gateway == "single"
  single_nat_gateway = true

  # Without NAT, the nodes (in public subnets) need a public IP to reach ECR, S3,
  # the LLM APIs and the control plane.
  map_public_ip_on_launch = local.nodes_in_public_subnets

  # These tags let the Kubernetes (LB) controllers find the subnets.
  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }
}
