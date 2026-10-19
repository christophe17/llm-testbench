variable "region" {
  description = "Région AWS principale du projet"
  type        = string
  default     = "eu-west-3"
}

variable "monthly_budget_usd" {
  description = "Plafond mensuel du budget AWS, en USD (AWS Budgets ne gère pas l'EUR ; 55 USD ~ 50 EUR)"
  type        = string
  default     = "55"
}

variable "alert_email" {
  description = "Adresse recevant les alertes de budget"
  type        = string
}

# --- Déploiement par GitHub Actions (github.tf) ---------------------------------------

variable "github_repository" {
  description = "Dépôt GitHub autorisé à assumer le rôle de déploiement (propriétaire/nom)"
  type        = string
  default     = "christophe17/llm-testbench"
}

variable "github_deploy_role_name" {
  description = "Nom du rôle IAM assumé par GitHub Actions ; envs/dev le retrouve par ce nom (eks.tf)"
  type        = string
  default     = "llm-testbench-github-deploy"
}

variable "ecr_repository_name" {
  description = "Dépôt ECR de l'image de l'API (envs/dev, ecr.tf)"
  type        = string
  default     = "llm-testbench-api"
}

variable "dev_environment_name" {
  description = "Préfixe des ressources de envs/dev (nom du cluster EKS et de l'instance RDS)"
  type        = string
  default     = "llm-testbench-dev"
}
