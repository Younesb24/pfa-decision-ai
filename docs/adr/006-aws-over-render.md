# ADR 006 — AWS as primary deploy, Render as kill-switch

**Status:** Accepted
**Date:** 2026-05-17

## Context

The MVP needs a public URL for the soutenance jury. Two viable hosts:

- **AWS** — ECS Fargate + RDS + ALB, fronted by Vercel for the Next.js app.
  Terraform skeleton already checked in under `terraform/` (Day 15).
- **Render.com** — single dashboard, deploy from git, managed Postgres, no IaC.

The plan budgets **one day** for the first deploy (Day 16). Beyond that, the
risk is sunk cost: every hour spent debugging IAM trust policies or
security-group ordering is an hour stolen from the Loom, the README, the
blog post, and the deck (Days 17–20).

## Decision

- **AWS is the primary target.** Terraform applied to a single `dev`
  workspace in `eu-west-3`. Public ALB DNS is acceptable for the jury demo —
  no custom domain, no ACM cert, no CloudFront.
- **Vercel hosts the Next.js dashboard** and proxies `/api/*` calls to the
  ALB DNS via `NEXT_PUBLIC_API_URL`. This avoids paying for an extra ECS
  task and gets us a CDN for free.
- **Render is the kill-switch.** If the AWS deploy is not green by
  **end of Day 16 + 12 h** (the morning of Day 17), abandon Terraform on a
  branch and ship to Render. The terraform files stay in-repo as a
  post-defense exercise. The defense story does not require AWS.
- **Render fallback shape:** one Web Service for the API (Dockerfile in
  `api/`), one Web Service for the dashboard (Dockerfile in `dashboard/`),
  one managed Postgres. Dagster is **dropped** in the kill-switch — the
  replay loop runs as a Render cron job hitting `/api/v1/replay/tick`.

## Consequences

**If AWS sticks (good case)**
- Real cloud bill, real IAM, real ALB, real RDS. Strong resume signal.
- Cost: ~$45/month at `dev` profile (db.t4g.micro + 1 vCPU ECS tasks +
  ALB minimum hours). Stoppable by `terraform destroy` after the defense.
- Future work: ACM cert + Route53, CloudFront in front of the dashboard,
  WAF, ECS auto-scaling. None of these block the defense.

**If Render kicks in (bad case)**
- Demo still works. The jury cannot tell from a URL bar whether the
  backend is on AWS Fargate or Render.
- Lose: Dagster orchestration in prod (cron job substitute is acceptable),
  Terraform on the live infra (file stays as DR plan).
- Acknowledge in the slides: "Day-16 budget was tight; production landed on
  Render. Terraform is in the repo for post-MVP cutover."

**Things we deliberately do NOT do for the MVP**
- Multi-region failover, blue/green, canary deploys.
- Per-environment AWS accounts. Single account, single region, one VPC.
- Self-hosted observability (CloudWatch logs + ALB metrics are enough).
- HTTPS via ACM. ALB DNS over HTTP is acceptable for the demo URL; the
  jury video does not show the address bar.

## Alternatives considered

- **Vercel + Supabase only.** Removes infra story entirely. Rejected because
  the project pitch is *data-platform-grade* — the jury asked specifically
  about pipeline orchestration and IaC.
- **Fly.io.** Cheaper than AWS, simpler than Render. Rejected only because
  Render is more familiar to the user; switching at Day 16 trades infra
  debt for tooling debt.
- **Self-hosted on the school VPN.** Rejected: the jury and external
  examiner must be able to reach the URL from outside campus.

## Operational notes

- **Bootstrap script** for the Terraform backend (S3 + DynamoDB lock table)
  is inlined as comments in `terraform/main.tf`. Run those two `aws` CLI
  commands **once**, then uncomment the `backend "s3"` block.
- **First-deploy failure modes** (expect to hit at least one):
  - ECS task can't pull the image → check the ECS execution role has
    `AmazonECSTaskExecutionRolePolicy` and ECR is in the same region.
  - Task fails health check → confirm
    `aws_lb_target_group.api.health_check.path = "/health"` and that the
    API actually binds `0.0.0.0:8000`, not `127.0.0.1`.
  - RDS unreachable → SG ordering. The RDS SG must allow inbound
    `5432` from the ECS task SG **by SG id**, not by CIDR.
- **EventBridge → API.** Use `aws_cloudwatch_event_api_destination`, not a
  raw `target.arn = aws_lb.main.arn`. The fix landed in `terraform/eventbridge.tf`
  alongside this ADR. The replay tick is gated by
  `enable_replay_schedule = false` until the first apply is healthy.

## Status review

Re-open this ADR if any of these become true post-defense:

- Monthly AWS bill exceeds $80 with no traffic (something is wrong).
- We add a second tenant or a second persona-domain (forces multi-account).
- The dashboard accepts user-generated content (need WAF + ACM + proper auth).
