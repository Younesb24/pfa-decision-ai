# Dev workspace overrides. Most knobs come from local.size_profile in main.tf.
# Copy this to terraform.staging.tfvars / terraform.prod.tfvars with real
# values before running `apply` against those workspaces.

aws_region           = "eu-west-3"
project_name         = "pfa"
image_repository_uri = "REPLACE_ME.dkr.ecr.eu-west-3.amazonaws.com/pfa"

# Tags — leave at "latest" for dev; CI flips to commit SHAs in staging/prod.
api_image_tag       = "latest"
dashboard_image_tag = "latest"
dagster_image_tag   = "latest"

# Leave anthropic_api_key blank in dev — the agent falls back to the
# deterministic template path. Set it before recording the soutenance Loom.
# anthropic_api_key = ""

# Dev only — the runtime warns at boot if this is the default. Override in
# staging/prod with `openssl rand -hex 32`.
jwt_secret = "pfa-dev-only-not-for-prod-2026"

# First apply: leave the EventBridge schedule off so the failure surface is
# just ECS + RDS + ALB. Flip to true (and set replay_tick_token) once the API
# target group is healthy on the public DNS.
enable_replay_schedule = false
# replay_tick_token = ""  # openssl rand -hex 32
