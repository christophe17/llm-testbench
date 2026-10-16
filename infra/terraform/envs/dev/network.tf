# Réseau. Le poste de coût dormant à surveiller est la NAT Gateway (~0,05 $/h + trafic) :
# `nat_gateway = "none"` place les nœuds en sous-réseaux publics (IP publique, groupe de
# sécurité fermé en entrée) et supprime ce coût — acceptable pour un dev éphémère.

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

  # Sans NAT, les nœuds (en public) ont besoin d'une IP publique pour joindre ECR, S3,
  # les API LLM et le plan de contrôle.
  map_public_ip_on_launch = local.nodes_in_public_subnets

  # Ces tags permettent aux contrôleurs Kubernetes (LB) de retrouver les sous-réseaux.
  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }
}
