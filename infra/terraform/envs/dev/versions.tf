terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.59"
    }
  }

  # The bucket is account-specific (suffix): it is passed through `-backend-config` from
  # the Makefile (`make infra-init`), never hard-coded here.
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
