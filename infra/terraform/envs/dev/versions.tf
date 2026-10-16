terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.59"
    }
  }

  # Le bucket est propre au compte (suffixe) : il est passé par `-backend-config` depuis
  # le Makefile (`make infra-init`), jamais écrit en dur ici.
  backend "s3" {
    key          = "envs/dev/terraform.tfstate"
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
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
