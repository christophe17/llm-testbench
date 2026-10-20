variable "region" {
  description = "AWS region (Paris: Bedrock serves Claude models there, to be checked per model)"
  type        = string
  default     = "eu-west-3"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "name" {
  description = "Resource prefix"
  type        = string
  default     = "llm-testbench-dev"
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "kubernetes_version" {
  description = "EKS version (standard support ~14 months; beyond that, extended support is billed)"
  type        = string
  default     = "1.33"
}

variable "node_instance_types" {
  description = "Graviton (arm64) nodes: same architecture as the image built on the M1 Mac"
  type        = list(string)
  default     = ["t4g.medium"]
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_max_size" {
  type    = number
  default = 3
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "nat_gateway" {
  description = "\"single\" (one NAT Gateway, ~$0.05/h) or \"none\" (nodes in public subnets, no NAT)"
  type        = string
  default     = "single"

  validation {
    condition     = contains(["single", "none"], var.nat_gateway)
    error_message = "nat_gateway must be \"single\" or \"none\"."
  }
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 20
}

variable "api_namespace" {
  type    = string
  default = "llm-testbench"
}

variable "api_service_account" {
  description = "Name of the API ServiceAccount (= name of the Helm release, chart llm-testbench-api)"
  type        = string
  default     = "api"
}

variable "external_secrets_namespace" {
  type    = string
  default = "external-secrets"
}

variable "public_access_cidrs" {
  description = <<-EOT
    CIDRs allowed on the public endpoint of the Kubernetes API. Open by default, and that is
    a deliberate choice (ADR 009, guide 09): authentication is IAM (access entries) and the
    GitHub Actions pipeline deploys from runners with variable IPs. Restrict to your IP/32 if
    you only deploy from your workstation (TF_VAR_public_access_cidrs='["a.b.c.d/32"]').
  EOT
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "github_deploy_role_name" {
  description = "Name of the GitHub Actions IAM role created by the bootstrap (github.tf); \"\" to not grant it cluster access"
  type        = string
  default     = "llm-testbench-github-deploy"
}
