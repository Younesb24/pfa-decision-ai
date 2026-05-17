# EventBridge → API replay tick.
#
# Every 15 min, EventBridge calls POST {ALB}/api/v1/replay/tick. The ALB is
# public, so we use EventBridge API Destinations rather than a VPC target.
# In dev the local Dagster schedule (`replay_schedule`) does the same job;
# this runs in prod where Dagster is single-task and we want a clock that
# survives a task restart.
#
# Toggle off during first apply to keep the failure surface small:
#   enable_replay_schedule = false
# Then flip to true once the API target group is healthy.

resource "aws_cloudwatch_event_connection" "replay_tick" {
  count              = var.enable_replay_schedule ? 1 : 0
  name               = "${local.name_prefix}-replay-tick-conn"
  description        = "API Destination connection for /replay/tick"
  authorization_type = "API_KEY"

  auth_parameters {
    api_key {
      key   = "X-Replay-Token"
      value = var.replay_tick_token
    }
  }
}

resource "aws_cloudwatch_event_api_destination" "replay_tick" {
  count                            = var.enable_replay_schedule ? 1 : 0
  name                             = "${local.name_prefix}-replay-tick-dest"
  description                      = "Target the replay-tick endpoint on the ALB"
  invocation_endpoint              = "http://${aws_lb.main.dns_name}/api/v1/replay/tick"
  http_method                      = "POST"
  invocation_rate_limit_per_second = 1
  connection_arn                   = aws_cloudwatch_event_connection.replay_tick[0].arn
}

resource "aws_iam_role" "eventbridge_invoke_api" {
  count = var.enable_replay_schedule ? 1 : 0
  name  = "${local.name_prefix}-eventbridge-invoke-api"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "events.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_invoke_api" {
  count = var.enable_replay_schedule ? 1 : 0
  name  = "${local.name_prefix}-eventbridge-invoke-api"
  role  = aws_iam_role.eventbridge_invoke_api[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "events:InvokeApiDestination"
      Resource = aws_cloudwatch_event_api_destination.replay_tick[0].arn
    }]
  })
}

resource "aws_cloudwatch_event_rule" "replay_tick" {
  count               = var.enable_replay_schedule ? 1 : 0
  name                = "${local.name_prefix}-replay-tick"
  description         = "Every 15 min, advance the synthetic replay clock"
  schedule_expression = "rate(15 minutes)"
}

resource "aws_cloudwatch_event_target" "replay_tick" {
  count = var.enable_replay_schedule ? 1 : 0

  rule      = aws_cloudwatch_event_rule.replay_tick[0].name
  target_id = "api-replay-tick"
  arn       = aws_cloudwatch_event_api_destination.replay_tick[0].arn
  role_arn  = aws_iam_role.eventbridge_invoke_api[0].arn

  input = jsonencode({
    source = "eventbridge"
    reason = "scheduled-replay-tick"
  })
}
