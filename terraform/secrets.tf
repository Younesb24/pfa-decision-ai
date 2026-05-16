# Secrets Manager entries pulled into the ECS task definition.
#
# `for_each` so a missing var.* simply skips creating the resource — useful
# in dev where ANTHROPIC_API_KEY is intentionally absent and the agent
# should fall back to the template path. In staging/prod a missing JWT
# secret should fail the plan, so it lives on the `required_secrets` map.

locals {
  optional_secrets = {
    for k, v in {
      anthropic-api-key = var.anthropic_api_key
    } : k => v if length(v) > 0
  }

  required_secrets = {
    jwt-secret = var.jwt_secret
  }
}

resource "aws_secretsmanager_secret" "optional" {
  for_each                = local.optional_secrets
  name                    = "${local.name_prefix}/${each.key}"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "optional" {
  for_each      = aws_secretsmanager_secret.optional
  secret_id     = each.value.id
  secret_string = local.optional_secrets[each.key]
}

resource "aws_secretsmanager_secret" "required" {
  for_each                = local.required_secrets
  name                    = "${local.name_prefix}/${each.key}"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "required" {
  for_each      = aws_secretsmanager_secret.required
  secret_id     = each.value.id
  secret_string = local.required_secrets[each.key]

  lifecycle {
    precondition {
      condition     = local.env == "dev" || length(local.required_secrets[each.key]) > 0
      error_message = "Required secret ${each.key} is empty — set the matching variable in terraform.${local.env}.tfvars."
    }
  }
}
