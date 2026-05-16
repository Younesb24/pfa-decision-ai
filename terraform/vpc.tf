# VPC + subnets.
#
# Uses the official terraform-aws-modules/vpc/aws module — building the VPC
# by hand is a hundred lines of route-table boilerplate that the module gets
# right. Public subnets host the ALB; private subnets host ECS tasks + RDS.
# A single NAT gateway is cheaper than one-per-AZ; flip
# `single_nat_gateway = false` in prod once the cross-AZ traffic justifies
# the extra ~$30/mo.

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.13"

  name = "${local.name_prefix}-vpc"
  cidr = var.vpc_cidr

  azs = var.azs
  # /20 = 4094 hosts each, plenty.
  public_subnets  = [for i, _ in var.azs : cidrsubnet(var.vpc_cidr, 4, i)]
  private_subnets = [for i, _ in var.azs : cidrsubnet(var.vpc_cidr, 4, i + 8)]

  enable_nat_gateway     = true
  single_nat_gateway     = local.env != "prod"
  one_nat_gateway_per_az = local.env == "prod"

  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Tier = "network"
  }
}
