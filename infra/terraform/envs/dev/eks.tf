# EKS : control plane 0,10 $/h — LA raison du make infra-up/down.
# Nœuds Graviton (arm64) en spot : cohérent avec les images buildées sur Apple Silicon.

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name               = var.name
  kubernetes_version = var.eks_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  endpoint_public_access                   = true
  enable_cluster_creator_admin_permissions = true

  eks_managed_node_groups = {
    default = {
      instance_types = ["t4g.medium"]
      ami_type       = "AL2023_ARM_64_STANDARD"
      capacity_type  = "SPOT"
      min_size       = 1
      max_size       = 3
      desired_size   = 2
    }
  }
}
