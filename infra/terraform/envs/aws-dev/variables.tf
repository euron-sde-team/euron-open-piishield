variable "region" {
  description = "AWS region."
  type        = string
}

variable "environment" {
  description = "Environment tag."
  type        = string
  default     = "dev"
}

variable "extra_tags" {
  description = "Tags added to every resource."
  type        = map(string)
  default     = {}
}

variable "name_prefix" {
  description = "Prefix for every resource name (at most 24 characters); the bucket name derives from it, so make it globally unique (e.g. \"acme-piishield-dev\")."
  type        = string
}

variable "hostname" {
  description = "Public host name of the dashboard and API, e.g. piishield-dev.example.com."
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate in the same region covering hostname."
  type        = string
}

variable "route53_zone_id" {
  description = "Hosted zone for the alias record and the DKIM records. Null: create them yourself (load_balancer_dns_name and dkim_records outputs)."
  type        = string
  default     = null
}

variable "mail_domain" {
  description = "Domain review and report notification mail is sent from (an SES domain identity), e.g. piishield-dev.example.com."
  type        = string
}

variable "mail_from_address" {
  description = "From address of PIIShield notification mail, on mail_domain (MAIL_FROM_ADDRESS), e.g. alerts@piishield-dev.example.com."
  type        = string
}

variable "mail_from_name" {
  description = "Display name on outgoing mail (MAIL_FROM_NAME)."
  type        = string
  default     = "PIIShield"
}

variable "signup_enabled" {
  description = "Let anyone create an organisation from the sign-up page (SIGNUP_ENABLED). Turn off once your organisation exists."
  type        = bool
  default     = false
}

variable "image_tag" {
  description = "Image tag the services run (the git commit or a release); the same tag for server and web."
  type        = string
}

variable "migrate_image_tag" {
  description = "Image tag of the one-off migrate task. Null: image_tag. scripts/aws-deploy.sh sets it to the new release while the services stay on the old one, migrates, then moves the services."
  type        = string
  default     = null
}

variable "alarm_email" {
  description = "Alarm notification address."
  type        = string
  default     = null
}

variable "api_extra_environment" {
  description = "Extra api and migrate environment (see docs/guides/configuration.md). Never secrets."
  type        = map(string)
  default     = {}
}

variable "backup_retention_days" {
  description = "Days a database backup in the exports bucket (backups/) is kept."
  type        = number
  default     = 14
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.small"
}

variable "cache_node_type" {
  description = "ElastiCache node type."
  type        = string
  default     = "cache.t4g.micro"
}

variable "metrics_allowed_cidrs" {
  description = "Source CIDRs allowed to scrape the api's /metrics through the load balancer."
  type        = list(string)
  default     = []
}
