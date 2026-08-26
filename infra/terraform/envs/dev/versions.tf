terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Backend partiel : le bucket est fourni par `terraform init -backend-config=...`
  # après le bootstrap (cf. ../../README.md).
  backend "s3" {
    key          = "dev/terraform.tfstate"
    region       = "eu-west-3"
    use_lockfile = true
    encrypt      = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "llm-testbench"
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}
