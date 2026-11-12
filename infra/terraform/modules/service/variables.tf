variable "name_prefix" {
  description = "Deployment prefix, e.g. \"piishield-prod\". At most 24 characters, so target group names stay unique within AWS's 32-character limit."
  type        = string
  validation {
    condition     = length(var.name_prefix) <= 24
    error_message = "name_prefix must be at most 24 characters."
  }
}

variable "vpc_id" {
  description = "VPC of the load balancer and the tasks."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnets for the load balancer."
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnets the tasks run in."
  type        = list(string)
}

variable "hostname" {
  description = "Public host name of the dashboard and API, e.g. piishield.example.com. The certificate must cover it."
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate (same region) for the HTTPS listener, covering hostname."
  type        = string
}

variable "route53_zone_id" {
  description = "Hosted zone to create the hostname alias record in. Null: point DNS at alb_dns_name yourself."
  type        = string
  default     = null
}

variable "server_image" {
  description = "Full server image reference (runs the api and migrate), e.g. <registry>/piishield-prod/server:<tag>."
  type        = string
}

variable "migrate_image" {
  description = "Image for the one-off migrate task. Null: server_image. A deploy sets it to the new release first, migrates, then moves the services (scripts/aws-deploy.sh)."
  type        = string
  default     = null
}

variable "web_image" {
  description = "Full web image reference, e.g. <registry>/piishield-prod/web:<tag>."
  type        = string
}

variable "container_port" {
  description = "Port the api and web containers listen on (PORT)."
  type        = number
  default     = 8080
}

variable "environment" {
  description = "Plain environment for api and migrate (PORT, PUBLIC_URL, PUBLIC_API_URL, EXPORTS_BUCKET and HTTP_KEEP_ALIVE_S are set by the module). Never secrets."
  type        = map(string)
  default     = {}
}

variable "web_environment" {
  description = "Plain environment for web (PORT, HOSTNAME, API_URL and API_INTERNAL_URL are set by the module). Never secrets."
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "Secrets injected into api and migrate: [{ name, valueFrom = \"<secret arn>:<json key>::\" }] (secrets module ecs_secrets)."
  type        = list(object({ name = string, valueFrom = string }))
  default     = []
}

variable "migrate_secrets" {
  description = "Extra secrets for the one-off migrate task only (secrets module bootstrap_secrets: PIISHIELD_ADMIN_PASSWORD for create-admin)."
  type        = list(object({ name = string, valueFrom = string }))
  default     = []
}

variable "kms_key_arn" {
  description = "CMK that backs the vault's envelope encryption, encrypts the exports bucket and the injected secrets."
  type        = string
}

variable "exports_bucket_arn" {
  description = "Exports bucket ARN (storage module bucket_arn)."
  type        = string
}

variable "exports_bucket_name" {
  description = "Exports bucket name (storage module bucket_name), passed as EXPORTS_BUCKET."
  type        = string
}

variable "db_security_group_id" {
  description = "Database security group; api and migrate get ingress on it."
  type        = string
}

variable "db_port" {
  description = "Database port."
  type        = number
  default     = 5432
}

variable "cache_security_group_id" {
  description = "Cache security group; api and migrate get ingress on it."
  type        = string
}

variable "cache_port" {
  description = "Cache port."
  type        = number
  default     = 6379
}

variable "log_group_names" {
  description = "CloudWatch log group per app: { api, web, migrate } (observability module log_group_names)."
  type        = map(string)
  validation {
    condition     = alltrue([for k in ["api", "web", "migrate"] : contains(keys(var.log_group_names), k)])
    error_message = "log_group_names needs api, web and migrate."
  }
}

variable "logs_kms_key_arn" {
  description = "CMK for the WAF log group. Null uses CloudWatch's default encryption."
  type        = string
  default     = null
}

variable "cpu_architecture" {
  description = "ARM64 (Graviton, cheaper) or X86_64. Images must be built for it."
  type        = string
  default     = "ARM64"
}

variable "container_insights" {
  description = "ECS Container Insights: enabled, enhanced or disabled."
  type        = string
  default     = "enabled"
}

variable "api_cpu" {
  description = "Fargate CPU units per api task."
  type        = number
  default     = 1024
}

variable "api_memory" {
  description = "Fargate memory (MiB) per api task."
  type        = number
  default     = 2048
}

variable "api_min_count" {
  description = "Minimum (and initial) api task count."
  type        = number
  default     = 2
}

variable "api_max_count" {
  description = "Maximum api task count under autoscaling. Equal to api_min_count disables scaling."
  type        = number
  default     = 6
}

variable "web_cpu" {
  description = "Fargate CPU units per web task."
  type        = number
  default     = 512
}

variable "web_memory" {
  description = "Fargate memory (MiB) per web task."
  type        = number
  default     = 1024
}

variable "web_min_count" {
  description = "Minimum (and initial) web task count."
  type        = number
  default     = 1
}

variable "web_max_count" {
  description = "Maximum web task count under autoscaling."
  type        = number
  default     = 3
}

variable "cpu_target_percent" {
  description = "Average CPU the autoscaler aims for (api and web)."
  type        = number
  default     = 60
}

variable "idle_timeout" {
  description = "Load balancer idle timeout in seconds, bounding how long a quiet connection (a large document upload or a slow AI-gateway restore call) stays open. The api's HTTP keep-alive is set 10 s above it."
  type        = number
  default     = 300
  validation {
    condition     = var.idle_timeout >= 60 && var.idle_timeout <= 4000
    error_message = "idle_timeout must be between 60 and 4000 seconds."
  }
}

variable "deletion_protection" {
  description = "Block accidental deletion of the load balancer."
  type        = bool
  default     = true
}

variable "access_logs_bucket" {
  description = "Existing bucket for load balancer access logs (needs the ELB log-delivery bucket policy). Null disables."
  type        = string
  default     = null
}

variable "metrics_allowed_cidrs" {
  description = "Source CIDRs allowed to read /metrics through the load balancer. Empty: /metrics answers 404 at the edge."
  type        = list(string)
  default     = []
}

variable "enable_waf" {
  description = "Attach a WAF web ACL (managed rule sets plus a per-IP flood guard) to the load balancer."
  type        = bool
  default     = true
}

variable "waf_rate_limit_per_5min" {
  description = "Requests per source IP per 5 minutes before WAF blocks. Keep it high: SDK backends often sit behind one NAT address."
  type        = number
  default     = 20000
}

variable "waf_log_retention_days" {
  description = "WAF log retention."
  type        = number
  default     = 30
}

# A boolean, not a null check on the policy: the policy is unknown until apply, and count
# must be decidable at plan time.
variable "send_mail" {
  description = "Attach mail_policy_json to the api task role (review queue and scan report notification mail through SES)."
  type        = bool
  default     = false
}

variable "mail_policy_json" {
  description = "IAM policy for sending mail (email module send_policy_json), with send_mail."
  type        = string
  default     = null
}
