terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
  # Local state (terraform.tfstate in this folder) — fine for a short-lived lab.
}

# AWS provider; credentials come from your AWS CLI profile / environment.
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project = "store-website-lab"
    }
  }
}
