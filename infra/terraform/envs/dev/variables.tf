variable "region" {
  description = "Région AWS (Paris : Bedrock y sert des modèles Claude, à vérifier par modèle)"
  type        = string
  default     = "eu-west-3"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "name" {
  description = "Préfixe des ressources"
  type        = string
  default     = "llm-testbench-dev"
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "kubernetes_version" {
  description = "Version EKS (support standard ~14 mois ; au-delà, support étendu facturé)"
  type        = string
  default     = "1.33"
}

variable "node_instance_types" {
  description = "Nœuds Graviton (arm64) : même architecture que l'image construite sur Mac M1"
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
  description = "\"single\" (une NAT Gateway, ~0,05 $/h) ou \"none\" (nœuds en sous-réseaux publics, sans NAT)"
  type        = string
  default     = "single"

  validation {
    condition     = contains(["single", "none"], var.nat_gateway)
    error_message = "nat_gateway doit valoir \"single\" ou \"none\"."
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
  description = "Nom du ServiceAccount de l'API (= nom de la release Helm, chart llm-testbench-api)"
  type        = string
  default     = "api"
}

variable "external_secrets_namespace" {
  type    = string
  default = "external-secrets"
}

variable "public_access_cidrs" {
  description = "CIDR autorisés sur l'endpoint public de l'API Kubernetes (votre IP/32 en pratique)"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
