# EventBridge → API replay tick.
#
# The local Dagster schedule (`replay_schedule`) drives this in dev. In prod
# the API has a /api/v1/replay/tick endpoint that EventBridge can hit
# directly via the ALB. This costs ~nothing — one HTTP call every 15 min —
# and keeps Dagster purely orchestral.
#
# Toggle off when iterating on infra to avoid noisy alarms:
#   enable_replay_schedule = false

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

  # API Destinations are the right primitive but require an HTTP API
  # Destination resource that depends on a connection. Skipped here to
  # keep the skeleton tractable; wire up `aws_cloudwatch_event_api_destination`
  # against the ALB endpoint when you ship.
  arn = aws_lb.main.arn
}
