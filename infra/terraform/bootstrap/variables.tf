variable "region" {
  description = "Main AWS region of the project"
  type        = string
  default     = "eu-west-3"
}

variable "monthly_budget_usd" {
  description = "Monthly AWS budget cap, in USD (AWS Budgets does not handle EUR; 55 USD ~ 50 EUR)"
  type        = string
  default     = "55"
}

variable "alert_email" {
  description = "Address receiving the budget alerts"
  type        = string
}

# --- Deployment through GitHub Actions (github.tf) -----------------------------------

variable "github_repository" {
  description = "GitHub repository allowed to assume the deployment role (owner/name)"
  type        = string
  default     = "christophe17/llm-testbench"
}

variable "github_deploy_role_name" {
  description = "Name of the IAM role assumed by GitHub Actions; envs/dev finds it by this name (eks.tf)"
  type        = string
  default     = "llm-testbench-github-deploy"
}

variable "ecr_repository_name" {
  description = "ECR repository of the API image (envs/dev, ecr.tf)"
  type        = string
  default     = "llm-testbench-api"
}

variable "dev_environment_name" {
  description = "Prefix of the envs/dev resources (name of the EKS cluster and of the RDS instance)"
  type        = string
  default     = "llm-testbench-dev"
}
