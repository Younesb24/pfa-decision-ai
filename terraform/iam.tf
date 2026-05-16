# IAM roles for ECS tasks.
#
# `execution_role` is what ECS itself assumes to pull images + log to CW.
# `task_role` is what code inside the container assumes if it needs to talk
# to other AWS services. The two are intentionally separate so a leak of
# the task role doesn't grant ECR / log permissions.

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_execution" {
  name               = "${local.name_prefix}-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "task_execution_default" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow the execution role to fetch the secrets we provision in secrets.tf.
# Resource ARN list is built from the actual secret resources so we don't
# grant access to anything we didn't create.
data "aws_iam_policy_document" "task_execution_secrets" {
  statement {
    actions = ["secretsmanager:GetSecretValue"]
    resources = concat(
      [aws_secretsmanager_secret.rds_password.arn],
      [for s in aws_secretsmanager_secret.optional : s.arn],
      [for s in aws_secretsmanager_secret.required : s.arn],
    )
  }
}

resource "aws_iam_role_policy" "task_execution_secrets" {
  name   = "${local.name_prefix}-task-execution-secrets"
  role   = aws_iam_role.task_execution.id
  policy = data.aws_iam_policy_document.task_execution_secrets.json
}

resource "aws_iam_role" "task" {
  name               = "${local.name_prefix}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

# Right now the application doesn't need any AWS-side permissions at
# runtime — once we wire up S3 for /ingest/upload, attach a policy here
# scoped to a single bucket prefix per env.
