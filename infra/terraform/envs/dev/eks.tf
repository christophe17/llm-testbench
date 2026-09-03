# EKS : plan de contrôle managé (0,10 $/h, le premier poste de coût), un groupe de nœuds
# managés Graviton, add-ons managés (dont l'agent Pod Identity et metrics-server pour
# l'HPA). Pas de Karpenter en phase 1 : un groupe de nœuds suffit, Karpenter arrive
# quand il y aura de quoi autoscaler (phase 5, générateur de trafic).

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.25"

  name               = var.name
  kubernetes_version = var.kubernetes_version

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = local.nodes_in_public_subnets ? module.vpc.public_subnets : module.vpc.private_subnets
  control_plane_subnet_ids = module.vpc.private_subnets

  endpoint_public_access       = true
  endpoint_public_access_cidrs = var.public_access_cidrs
  endpoint_private_access      = true

  # Access entries (le mécanisme actuel ; aws-auth est en voie de disparition) :
  # le créateur du cluster devient administrateur, sans ConfigMap à éditer.
  authentication_mode                      = "API"
  enable_cluster_creator_admin_permissions = true

  enable_irsa         = true # gardé pour les charts qui ne parlent pas encore Pod Identity
  create_kms_key      = true
  deletion_protection = false # `make infra-down` doit pouvoir tout détruire

  cloudwatch_log_group_retention_in_days = 7
  enabled_log_types                      = ["api", "audit", "authenticator"]

  addons = {
    coredns                = {}
    kube-proxy             = {}
    vpc-cni                = { before_compute = true }
    eks-pod-identity-agent = { before_compute = true }
    metrics-server         = {}
  }

  eks_managed_node_groups = {
    default = {
      ami_type       = "AL2023_ARM_64_STANDARD"
      instance_types = var.node_instance_types
      min_size       = var.node_min_size
      max_size       = var.node_max_size
      desired_size   = var.node_desired_size
      disk_size      = 30
    }
  }

  tags = {
    Module = "eks"
  }
}
