# RDS Postgres 15.
#
# Random password stored in Secrets Manager — the ECS task definition pulls
# it into the container via the `secrets` block, so the plaintext never
# touches CloudFormation outputs or `terraform show`. db_subnet_group keeps
# the instance off the public subnets; only the ECS task SG can reach 5432.

resource "random_password" "rds" {
  length           = 32
  special          = true
  override_special = "!#%^*()-_=+[]{}<>?"
}

resource "aws_secretsmanager_secret" "rds_password" {
  name                    = "${local.name_prefix}/rds-password"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "rds_password" {
  secret_id     = aws_secretsmanager_secret.rds_password.id
  secret_string = random_password.rds.result
}

resource "aws_db_subnet_group" "postgres" {
  name       = "${local.name_prefix}-rds-subnets"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "rds" {
  name        = "${local.name_prefix}-rds"
  description = "Postgres ingress from ECS tasks only"
  vpc_id      = module.vpc.vpc_id
}

# Ingress wired up in ecs.tf where the task SG is defined (avoid cycles).
resource "aws_security_group_rule" "rds_egress_all" {
  type              = "egress"
  security_group_id = aws_security_group.rds.id
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
}

resource "aws_db_instance" "postgres" {
  identifier             = "${local.name_prefix}-postgres"
  engine                 = "postgres"
  engine_version         = "15.6"
  instance_class         = local.size.rds_instance_class
  allocated_storage      = local.size.rds_allocated_gb
  storage_type           = "gp3"
  storage_encrypted      = true
  db_name                = "pfa_olist"
  username               = var.rds_username
  password               = random_password.rds.result
  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  multi_az               = local.env == "prod"
  publicly_accessible    = false
  skip_final_snapshot    = local.env != "prod"
  deletion_protection    = local.env == "prod"
  apply_immediately      = local.env == "dev"

  # Cheap but real — point-in-time recovery for prod; nothing in dev.
  backup_retention_period = local.env == "prod" ? 7 : 0

  performance_insights_enabled = local.env == "prod"
}
