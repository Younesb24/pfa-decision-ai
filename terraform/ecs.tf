# ECS Fargate — cluster + three services.
#
# Task definitions intentionally keep `desired_count = local.size.desired_count`
# so we can scale by editing main.tf locals rather than chasing each service.
# Logs go to a single log group per service so CloudWatch Insights queries
# stay simple.

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = local.env == "prod" ? "enabled" : "disabled"
  }
}

# ── Shared task SG. Allows the ALB to hit each task port, and the task to
#    reach the RDS instance on 5432. Anything else egresses to the NAT.
resource "aws_security_group" "task" {
  name        = "${local.name_prefix}-task"
  description = "ECS task ingress from ALB; egress to anywhere"
  vpc_id      = module.vpc.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group_rule" "alb_to_task_api" {
  type                     = "ingress"
  security_group_id        = aws_security_group.task.id
  source_security_group_id = aws_security_group.alb.id
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
}

resource "aws_security_group_rule" "alb_to_task_dashboard" {
  type                     = "ingress"
  security_group_id        = aws_security_group.task.id
  source_security_group_id = aws_security_group.alb.id
  from_port                = 3000
  to_port                  = 3000
  protocol                 = "tcp"
}

resource "aws_security_group_rule" "alb_to_task_dagster" {
  type                     = "ingress"
  security_group_id        = aws_security_group.task.id
  source_security_group_id = aws_security_group.alb.id
  from_port                = 3001
  to_port                  = 3001
  protocol                 = "tcp"
}

resource "aws_security_group_rule" "task_to_rds" {
  type                     = "ingress"
  security_group_id        = aws_security_group.rds.id
  source_security_group_id = aws_security_group.task.id
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
}

# ── Log groups ──────────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name_prefix}/api"
  retention_in_days = local.size.log_retention_days
}

resource "aws_cloudwatch_log_group" "dashboard" {
  name              = "/ecs/${local.name_prefix}/dashboard"
  retention_in_days = local.size.log_retention_days
}

resource "aws_cloudwatch_log_group" "dagster" {
  name              = "/ecs/${local.name_prefix}/dagster"
  retention_in_days = local.size.log_retention_days
}

# ── Task definitions ────────────────────────────────────────────────────

# Helper: secret references the API task pulls.
locals {
  api_secrets = concat(
    [
      { name = "POSTGRES_PASSWORD", valueFrom = aws_secretsmanager_secret.rds_password.arn },
      { name = "JWT_SECRET", valueFrom = aws_secretsmanager_secret.required["jwt-secret"].arn },
    ],
    contains(keys(aws_secretsmanager_secret.optional), "anthropic-api-key")
      ? [{ name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.optional["anthropic-api-key"].arn }]
      : []
  )
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name_prefix}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = local.size.task_cpu
  memory                   = local.size.task_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "${var.image_repository_uri}/api:${var.api_image_tag}"
      essential = true
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = [
        { name = "POSTGRES_HOST", value = aws_db_instance.postgres.address },
        { name = "POSTGRES_PORT", value = "5432" },
        { name = "POSTGRES_DB", value = aws_db_instance.postgres.db_name },
        { name = "POSTGRES_USER", value = var.rds_username },
      ]
      secrets = local.api_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "curl -fsS http://localhost:8000/health || exit 1"]
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
    }
  ])
}

resource "aws_ecs_task_definition" "dashboard" {
  family                   = "${local.name_prefix}-dashboard"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = local.size.task_cpu
  memory                   = local.size.task_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "dashboard"
      image     = "${var.image_repository_uri}/dashboard:${var.dashboard_image_tag}"
      essential = true
      portMappings = [{ containerPort = 3000, protocol = "tcp" }]
      environment = [
        # Note: this is also baked at build time. If the URL changes, rebuild
        # the image — Next inlines NEXT_PUBLIC_* into client bundles.
        { name = "NEXT_PUBLIC_API_URL", value = "http://${aws_lb.main.dns_name}/api/v1" },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.dashboard.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "dashboard"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "dagster" {
  family                   = "${local.name_prefix}-dagster"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = local.size.task_cpu
  memory                   = local.size.task_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "dagster"
      image     = "${var.image_repository_uri}/dagster:${var.dagster_image_tag}"
      essential = true
      portMappings = [{ containerPort = 3001, protocol = "tcp" }]
      environment = [
        { name = "POSTGRES_HOST", value = aws_db_instance.postgres.address },
        { name = "POSTGRES_PORT", value = "5432" },
        { name = "POSTGRES_DB", value = aws_db_instance.postgres.db_name },
        { name = "POSTGRES_USER", value = var.rds_username },
      ]
      secrets = [
        { name = "POSTGRES_PASSWORD", valueFrom = aws_secretsmanager_secret.rds_password.arn },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.dagster.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "dagster"
        }
      }
    }
  ])
}

# ── Services ────────────────────────────────────────────────────────────

resource "aws_ecs_service" "api" {
  name            = "${local.name_prefix}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = local.size.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]
}

resource "aws_ecs_service" "dashboard" {
  name            = "${local.name_prefix}-dashboard"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.dashboard.arn
  desired_count   = local.size.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.dashboard.arn
    container_name   = "dashboard"
    container_port   = 3000
  }

  depends_on = [aws_lb_listener.http]
}

resource "aws_ecs_service" "dagster" {
  name            = "${local.name_prefix}-dagster"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.dagster.arn
  desired_count   = 1  # never need more than one — it's the orchestrator UI
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.dagster.arn
    container_name   = "dagster"
    container_port   = 3001
  }

  depends_on = [aws_lb_listener.http]
}
