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
