# AWS bootstrap — the only cloud infra of phase 0 (ADR 002):
#   1. encrypted, versioned S3 bucket for the Terraform state of future environments;
#   2. monthly budget alert, so that no idle cost item goes unnoticed.
#
# Chicken-and-egg problem: this module creates the state bucket, so it cannot store its
# own state there. Its state stays LOCAL (a few stable resources, acceptable), and it is
# run only once: `make bootstrap-apply`.
#
# The EKS / ECR / RDS / network modules arrive in phase 1, with an S3 backend on this bucket.

terraform {
  required_version = ">= 1.10" # native S3 state locking (use_lockfile), no DynamoDB

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
  # Account suffix for the global uniqueness of bucket names
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
      sse_algorithm = "aws:kms" # AWS-managed key (aws/s3): encrypted, zero custom KMS cost
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

# AWS Budgets charges nothing for the first 2 budgets and only speaks USD:
# 55 USD ~ 50 EUR (threshold approved on 2026-08-26, adjust in variables.tf).
resource "aws_budgets_budget" "monthly" {
  name         = "llm-testbench-monthly"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Alert on actual spend at 80% and 100%, and on forecast at 100%:
  # the forecast fires days before actual spend breaks through the cap.
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
