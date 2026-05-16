output "alb_dns_name" {
  description = "Public DNS of the ALB. Hit it on :80 once services are healthy."
  value       = aws_lb.main.dns_name
}

output "rds_endpoint" {
  description = "Postgres endpoint. Reachable only from inside the VPC."
  value       = aws_db_instance.postgres.address
}

output "rds_password_secret_arn" {
  description = "Pull with: aws secretsmanager get-secret-value --secret-id <arn>"
  value       = aws_secretsmanager_secret.rds_password.arn
}

output "ecs_cluster_name" {
  description = "ECS cluster name — useful for `aws ecs execute-command` and run-task overrides."
  value       = aws_ecs_cluster.main.name
}

output "log_groups" {
  description = "CloudWatch log groups for the three services."
  value = {
    api       = aws_cloudwatch_log_group.api.name
    dashboard = aws_cloudwatch_log_group.dashboard.name
    dagster   = aws_cloudwatch_log_group.dagster.name
  }
}
