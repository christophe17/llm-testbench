# Bootstrap AWS — la seule infra cloud de la phase 0 (ADR 002) :
#   1. bucket S3 chiffré et versionné pour l'état Terraform des environnements futurs ;
#   2. alerte de budget mensuelle, pour qu'aucun poste dormant ne passe inaperçu.
#
# Problème de l'œuf et de la poule : ce module crée le bucket d'état, il ne peut donc
# pas y stocker le sien. Son état reste LOCAL (quelques ressources stables, acceptable),
# et il ne se lance qu'une fois : `make bootstrap-apply`.
#
# Les modules EKS / ECR / RDS / réseau arrivent en phase 1, avec backend S3 sur ce bucket.

terraform {
  required_version = ">= 1.10" # verrouillage d'état S3 natif (use_lockfile), sans DynamoDB

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "llm-testbench"
      ManagedBy = "terraform"
      Module    = "bootstrap"
    }
  }
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "tfstate" {
  # Suffixe compte pour l'unicité globale des noms de bucket
  bucket = "llm-testbench-tfstate-${data.aws_caller_identity.current.account_id}"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms" # clé gérée AWS (aws/s3) : chiffré, zéro coût de KMS custom
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# AWS Budgets ne facture rien pour les 2 premiers budgets et ne parle qu'en USD :
# 55 USD ~ 50 EUR (seuil validé le 2026-08-26, à ajuster dans variables.tf).
resource "aws_budgets_budget" "monthly" {
  name         = "llm-testbench-monthly"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Alerte au réel à 80 % et 100 %, et au prévisionnel à 100 % :
  # le prévisionnel se déclenche des jours avant que le réel ne crève le plafond.
  dynamic "notification" {
    for_each = [
      { threshold = 80, type = "ACTUAL" },
      { threshold = 100, type = "ACTUAL" },
      { threshold = 100, type = "FORECASTED" },
    ]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value.threshold
      threshold_type             = "PERCENTAGE"
      notification_type          = notification.value.type
      subscriber_email_addresses = [var.alert_email]
    }
  }
}
