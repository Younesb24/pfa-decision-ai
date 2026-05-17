variable "project_name" {
  description = "Short prefix used in resource names + Project tag."
  type        = string
  default     = "pfa"
}

variable "aws_region" {
  description = "AWS region. eu-west-3 (Paris) is the default since PFA is hosted in France."
  type        = string
  default     = "eu-west-3"
}

variable "vpc_cidr" {
  description = "Top-level CIDR for the VPC. Sized for /16 to leave room for future subnets."
  type        = string
  default     = "10.42.0.0/16"
}

variable "azs" {
  description = "Availability zones. Two is the minimum for an ALB; bump to three for prod-grade HA."
  type        = list(string)
  default     = ["eu-west-3a", "eu-west-3b"]
}

variable "image_repository_uri" {
  description = "Base ECR repo URI without tag, e.g. 123456.dkr.ecr.eu-west-3.amazonaws.com/pfa"
  type        = string
}

variable "api_image_tag" {
  description = "Tag for the API image. CI updates this on each main merge."
  type        = string
  default     = "latest"
}

variable "dashboard_image_tag" {
  description = "Tag for the dashboard image."
  type        = string
  default     = "latest"
}

variable "dagster_image_tag" {
  description = "Tag for the Dagster image."
  type        = string
  default     = "latest"
}

variable "rds_username" {
  description = "Master username on the RDS instance."
  type        = string
  default     = "pfa"
}

variable "anthropic_api_key" {
  description = <<-EOT
    Optional. If provided, written to Secrets Manager; the API task pulls it
    via the secrets stanza. Leave blank in dev to run the agent in offline
    fallback (responses come from the deterministic template path).
  EOT
  type        = string
  sensitive   = true
  default     = ""
}

variable "jwt_secret" {
  description = "JWT signing secret. Must be set in staging/prod. Default fallback is for dev only."
  type        = string
  sensitive   = true
  default     = ""
}

variable "enable_replay_schedule" {
  description = "Whether to create the EventBridge rule that pings /replay/tick every 15 min."
  type        = bool
  default     = false
}

variable "replay_tick_token" {
  description = <<-EOT
    Shared secret EventBridge sends as X-Replay-Token on the /replay/tick
    call. The API verifies it before advancing the replay clock so a random
    internet hit can't drive the loop. Generate with `openssl rand -hex 32`.
  EOT
  type        = string
  sensitive   = true
  default     = ""
}
