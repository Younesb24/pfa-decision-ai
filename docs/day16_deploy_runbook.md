# Day 16 — first deploy runbook

> Public URL is the only Day-16 success criterion. AWS is plan A; Render is
> plan B. The cut-over rule is in [ADR-006](adr/006-aws-over-render.md).

## Pre-flight (do these once, ever)

```powershell
# 1. AWS CLI logged in, region pinned.
aws configure list
aws sts get-caller-identity     # must succeed
$env:AWS_DEFAULT_REGION = "eu-west-3"

# 2. Terraform backend (S3 + DynamoDB lock).
aws s3api create-bucket --bucket pfa-tfstate `
  --create-bucket-configuration LocationConstraint=eu-west-3
aws s3api put-bucket-versioning --bucket pfa-tfstate `
  --versioning-configuration Status=Enabled
aws dynamodb create-table --table-name pfa-tflock `
  --attribute-definitions AttributeName=LockID,AttributeType=S `
  --key-schema AttributeName=LockID,KeyType=HASH `
  --billing-mode PAY_PER_REQUEST

# 3. ECR repo for the three images.
aws ecr create-repository --repository-name pfa
```

After the backend exists, uncomment the `backend "s3"` block in
`terraform/main.tf` (it's already templated there).

## Build & push images

```powershell
$REGION    = "eu-west-3"
$ACCOUNT   = (aws sts get-caller-identity --query Account --output text)
$REPO      = "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/pfa"

aws ecr get-login-password --region $REGION `
  | docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"

# API
docker build -t "$REPO:api-latest" -f api/Dockerfile .
docker push "$REPO:api-latest"

# Dashboard — bake the public API URL at build time (Next inlines it).
# Re-run this step once you know the ALB DNS, and update with that value.
docker build `
  --build-arg NEXT_PUBLIC_API_URL="http://placeholder-alb.example.com" `
  -t "$REPO:dashboard-latest" -f dashboard/Dockerfile .
docker push "$REPO:dashboard-latest"

# Dagster
docker build -t "$REPO:dagster-latest" -f dagster_pipeline/Dockerfile .
docker push "$REPO:dagster-latest"
```

Set `image_repository_uri` in `terraform.dev.tfvars` to `$REPO`.

## Terraform apply

```powershell
cd terraform

terraform init                          # backend + providers
terraform workspace new dev
terraform workspace select dev
terraform plan  -var-file=terraform.dev.tfvars -out=dev.tfplan
# READ EVERY DIFF LINE BEFORE APPLYING. ALB + RDS + ECS = expensive mistakes.
terraform apply dev.tfplan              # ~12–15 min, RDS is the bottleneck

terraform output                        # alb_dns_name + ecr_repo
```

## Smoke test the live stack

```powershell
$ALB = (terraform -chdir=terraform output -raw alb_dns_name)

# 1. ALB is reachable.
curl "http://$ALB/api/health"           # → {"status":"healthy","service":"pfa-decision-ai"}

# 2. Login works (seed users must already be in RDS — see DB seed step below).
$body = @{ email = "ops@pfa.local"; password = "ops123" } | ConvertTo-Json
$tok  = (curl -X POST "http://$ALB/api/v1/auth/login" -H "Content-Type: application/json" -d $body).access_token

# 3. KPI summary returns rows.
curl "http://$ALB/api/v1/kpi/summary?persona=ops" -H "Authorization: Bearer $tok"

# 4. Dashboard SPA loads.
curl -I "http://$ALB/"                  # 200, content-type: text/html
```

If steps 1–4 are all green, the AWS leg is done. **Stop here.** Move to
Vercel.

## Seed the live RDS

```powershell
# Get the master password from Secrets Manager (terraform put it there).
$SECRET = (aws secretsmanager get-secret-value `
  --secret-id (terraform -chdir=terraform output -raw rds_password_secret_arn) `
  --query SecretString --output text | ConvertFrom-Json)

$env:DATABASE_URL = "postgresql://$($SECRET.username):$($SECRET.password)@$($SECRET.host):5432/pfa_olist"

# Through a short-lived session-manager tunnel or jump box. Direct connect
# only works if your IP is whitelisted in the RDS SG (it isn't by default).
psql $env:DATABASE_URL -f scripts/users_migration.sql
psql $env:DATABASE_URL -f scripts/source_registry_migration.sql
psql $env:DATABASE_URL -f scripts/audit_log_migration.sql
psql $env:DATABASE_URL -f scripts/replay_state_migration.sql
python scripts/seed_users.py
python scripts/load_bronze.py
cd dbt_project && dbt run --profiles-dir . && dbt test --profiles-dir . && cd ..
```

## Front the dashboard with Vercel (optional but recommended)

1. `vercel link` from the `dashboard/` directory.
2. Set `NEXT_PUBLIC_API_URL = http://<ALB_DNS>` in Vercel env vars.
3. `vercel --prod`. Vercel returns the public HTTPS URL.
4. Update `api/.env` `CORS_ORIGINS` to include the Vercel domain.
5. Re-deploy the API ECS task so CORS picks up.

## Turn on the replay schedule

```powershell
# Generate a token, put it in Secrets Manager, wire to ECS env.
$TOKEN = (-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | % { [char]$_ }))
aws secretsmanager put-secret-value --secret-id pfa-replay-tick-token --secret-string $TOKEN

# Flip terraform on:
#   enable_replay_schedule = true
#   replay_tick_token      = "<TOKEN>"   (read from Secrets Manager in real life)
terraform plan -var-file=terraform.dev.tfvars
terraform apply
```

EventBridge will start hitting `/api/v1/replay/tick` every 15 minutes.
Verify in CloudWatch Logs that the API logs `replay tick succeeded`.

## Kill-switch — Render fallback

Trigger if Day 16 is **>12 hours over budget** (i.e. it's the morning of
Day 17 and `curl /api/health` is still red). Per ADR-006, this is acceptable.

```powershell
# 1. New Render account, link the GitHub repo.
# 2. Two Web Services + one Postgres:
#    api/        → Dockerfile,  port 8000
#    dashboard/  → Dockerfile,  port 3000, env NEXT_PUBLIC_API_URL=<api-render-url>
#    postgres    → managed (free tier ok)
# 3. Render Cron Job (15 min):
#    curl -fsS -X POST "$API/api/v1/replay/tick" -H "X-Replay-Token: $TOKEN"
# 4. Re-seed the Render DB with the same scripts as the AWS leg.
```

No Dagster on Render — the cron job replaces the schedule. Note in the
slides and the README that the production deploy fell back to Render
per ADR-006.

## Common first-deploy failures

| Symptom | Probable cause | Fix |
|---|---|---|
| ECS task stuck in `PROVISIONING` | Image pull failed | Confirm execution role has `AmazonECSTaskExecutionRolePolicy`, ECR repo region matches |
| ECS task starts then dies in 30s | Health-check path wrong / app binds 127.0.0.1 | API must `uvicorn --host 0.0.0.0`. Confirm `aws_lb_target_group.api.health_check.path = "/health"` |
| API task healthy, `/api/v1/kpi/summary` 500 | RDS SG blocks ECS task SG | RDS SG inbound rule must reference the ECS task SG by id, not CIDR |
| Dashboard renders but `Failed to fetch /api/*` | Wrong `NEXT_PUBLIC_API_URL` baked in | Rebuild the dashboard image with the correct URL — Next inlines it at build time |
| `/api/v1/replay/tick` always 401 from EventBridge | Token mismatch | Compare `REPLAY_TICK_TOKEN` env on the ECS task definition vs. the `aws_cloudwatch_event_connection.replay_tick` API key value |

## Done when

- [ ] `curl http://<public-url>/api/health` returns 200.
- [ ] `POST /api/v1/auth/login` with `ops@pfa.local / ops123` returns a JWT.
- [ ] Dashboard loads at the public URL and sign-in succeeds end-to-end.
- [ ] At least one OODA-loop walkthrough is reproducible from the public URL.
- [ ] ADR-006 is up to date with whichever host won (AWS or Render).
