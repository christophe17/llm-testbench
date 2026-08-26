variable "region" {
  type    = string
  default = "eu-west-3"
}

variable "name" {
  description = "Préfixe de nommage de toutes les ressources."
  type        = string
  default     = "llm-testbench-dev"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "eks_version" {
  description = "Version Kubernetes du control plane EKS."
  type        = string
  default     = "1.33"
}

variable "db_password" {
  description = "Mot de passe maître RDS — fourni via TF_VAR_db_password, jamais commité."
  type        = string
  sensitive   = true
}
