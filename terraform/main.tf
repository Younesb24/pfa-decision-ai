terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state is mandatory before this hits a shared environment.
  # Uncomment after creating the bucket + lock table. Bootstrap script:
  #   aws s3api create-bucket --bucket pfa-tfstate --region eu-west-3 \
  #     --create-bucket-configuration LocationConstraint=eu-west-3
  #   aws dynamodb create-table --table-name pfa-tflock \
  #     --attribute-definitions AttributeName=LockID,AttributeType=S \
  #     --key-schema AttributeName=LockID,KeyType=HASH \
  #     --billing-mode PAY_PER_REQUEST
  #
  # backend "s3" {
  #   bucket         = "pfa-tfstate"
  #   key            = "pfa/terraform.tfstate"
  #   region         = "eu-west-3"
  #   dynamodb_table = "pfa-tflock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = terraform.workspace
      ManagedBy   = "terraform"
    }
  }
}

# A bit of locals so workspaces can swap sizing without forking the file.
locals {
  env = terraform.workspace

  # Per-env knobs. Bigger boxes, more replicas, longer log retention in prod.
  size_profile = {
    dev = {
      rds_instance_class = "db.t4g.micro"
      rds_allocated_gb   = 20
      task_cpu           = 256
      task_memory        = 512
      desired_count      = 1
      log_retention_days = 7
    }
    staging = {
      rds_instance_class = "db.t4g.small"
      rds_allocated_gb   = 50
      task_cpu           = 512
      task_memory        = 1024
      desired_count      = 1
      log_retention_days = 14
    }
    prod = {
      rds_instance_class = "db.t4g.medium"
      rds_allocated_gb   = 100
      task_cpu           = 1024
      task_memory        = 2048
      desired_count      = 2
      log_retention_days = 30
    }
  }

  size = local.size_profile[local.env]

  name_prefix = "${var.project_name}-${local.env}"
}
