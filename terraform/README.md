# Terraform — PFA Decision AI

Skeleton infrastructure for deploying the FastAPI + dashboard + Dagster
stack on AWS. Three Terraform workspaces are supported out of the box:
`dev`, `staging`, `prod`. They share this configuration; per-env
overrides live in `terraform.<env>.tfvars`.

```
terraform init
terraform workspace new dev      # one-off
terraform workspace select dev
terraform plan  -var-file=terraform.dev.tfvars
terraform apply -var-file=terraform.dev.tfvars
```

## Honest status

This is a Day-15 skeleton. **It has not been `apply`d against a real AWS
account.** The shape is right; the wiring details (security-group rules,
target-group health-check paths, secrets format on the ECS task) are the
kind of thing you'll iterate on during the Day-16 first deploy. The point
of checking it in is so Day 16 starts from a real foundation rather than
a blank `main.tf`.

## What this provisions

| Resource | File | Note |
|---|---|---|
| VPC + 2 public + 2 private subnets across 2 AZs | `vpc.tf` | Uses the official `terraform-aws-modules/vpc` module |
| RDS Postgres 15 (db.t4g.micro by default) | `rds.tf` | Private subnet, encrypted, KMS-managed password |
| ECS Fargate cluster + service for `api`, `dashboard`, `dagster` | `ecs.tf` | Tasks pull images from ECR (you push them) |
| Application Load Balancer | `alb.tf` | Routes `/` to dashboard, `/api/v1/*` to api, `/orchestrator/*` to dagster |
| Secrets Manager for JWT, DB password, ANTHROPIC_API_KEY | `secrets.tf` | Tasks pull via IAM, never via env-file copy |
| Task IAM role + execution role | `iam.tf` | Read-only on secrets, write on CloudWatch logs |
| EventBridge rule to invoke `/api/v1/replay/tick` every 15 min | `eventbridge.tf` | Optional — disable with `enable_replay_schedule = false` |

## What it deliberately does NOT do

- **CloudFront / Vercel front**: the handoff plan puts the dashboard on
  Vercel pointing at the AWS ALB. The Terraform here only stands up the
  ALB; Vercel config lives outside Terraform.
- **Custom domain / ACM cert**: add an `aws_acm_certificate` + Route53
  record after you've picked a domain.
- **Auto-scaling**: the services are fixed at `desired_count = 1` in dev.
  Bump min/max in `ecs.tf` once you have load curves.
- **Bastion / VPN**: RDS is reachable only from the ECS tasks. Use a
  short-lived EC2 jump box (or session-manager) when you need a `psql`.
- **CI/CD**: assumed to live in GitHub Actions (separate repo file). The
  workflow needs `AWS_OIDC_ROLE_ARN`; the role itself is defined here.

## Pre-flight before first apply

1. Push the three Docker images to ECR (or set `image_tag = "latest"` and
   build/push from CI). The Dockerfiles in `api/`, `dashboard/`,
   `dagster_pipeline/` are what we built on Day 14.
2. Create an S3 bucket + DynamoDB lock table for the backend. Wire them
   up by uncommenting the `backend "s3"` block in `main.tf`.
3. `terraform.tfvars`: at minimum `project_name`, `aws_region`,
   `image_repository_uri` (e.g. `123.dkr.ecr.eu-west-3.amazonaws.com/pfa`).
4. Plan, read every diff, then apply. Expect 12–15 minutes for the first
   apply (RDS is slow).

## Kill-switch

If Day 15 burns >2 days per the handoff, abandon Terraform and ship to
Render.com instead. Keep these files on a branch for after the defense.
