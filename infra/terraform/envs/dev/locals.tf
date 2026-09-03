locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2)

  # Trois familles de sous-réseaux par AZ : publics (LB, NAT), privés (nœuds), base (RDS).
  public_subnets   = [for i, az in local.azs : cidrsubnet(var.vpc_cidr, 8, i)]
  private_subnets  = [for i, az in local.azs : cidrsubnet(var.vpc_cidr, 8, 10 + i)]
  database_subnets = [for i, az in local.azs : cidrsubnet(var.vpc_cidr, 8, 20 + i)]

  nodes_in_public_subnets = var.nat_gateway == "none"

  secret_prefix = "llm-testbench/${var.environment}"
  api_secrets = {
    "anthropic-api-key"  = "ANTHROPIC_API_KEY"
    "openai-api-key"     = "OPENAI_API_KEY"
    "openrouter-api-key" = "OPENROUTER_API_KEY"
  }
}

data "aws_availability_zones" "available" {
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

data "aws_caller_identity" "current" {}
