# EKS: managed control plane ($0.10/h, the largest cost item), a managed Graviton node
# group, managed add-ons (including the Pod Identity agent and metrics-server for the
# HPA). No Karpenter in phase 1: one node group is enough, Karpenter arrives when there
# is something to autoscale (phase 5, traffic generator).

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

  # Access entries (the current mechanism; aws-auth is being phased out):
  # the cluster creator becomes administrator, with no ConfigMap to edit.
  authentication_mode                      = "API"
  enable_cluster_creator_admin_permissions = true

  # The GitHub Actions deployment role (bootstrap, github.tf) becomes administrator of the
  # dev cluster, for the duration of a `helm upgrade`. The least-privilege answer (EditPolicy
  # scoped to the namespace, plus a ClusterRole for the External Secrets CRDs) is in guide 09.
  access_entries = var.github_deploy_role_name == "" ? {} : {
    github_deploy = {
      principal_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.github_deploy_role_name}"
      policy_associations = {
        admin = {
          policy_arn   = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = { type = "cluster" }
        }
      }
    }
  }

  enable_irsa         = true # kept for the charts that do not speak Pod Identity yet
  create_kms_key      = true
  deletion_protection = false # `make infra-down` must be able to destroy everything

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
