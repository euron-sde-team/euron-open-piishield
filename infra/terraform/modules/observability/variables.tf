variable "name_prefix" {
  description = "Prefix for every resource name."
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention for the app log groups."
  type        = number
  default     = 30
}

variable "logs_kms_key_arn" {
  description = "CMK for the log groups (its key policy must allow CloudWatch Logs, as the kms module's does). Null uses CloudWatch's default encryption."
  type        = string
  default     = null
}

variable "alarm_email" {
  description = "Address subscribed to alarm notifications (confirm the e-mail AWS sends). Null: subscribe something else to the topic."
  type        = string
  default     = null
}

variable "alb_arn_suffix" {
  description = "Load balancer ARN suffix."
  type        = string
}

variable "ecs_cluster_name" {
  description = "ECS cluster name."
  type        = string
}

variable "lb_services" {
  description = "Load-balanced services (service module `services`): { api = { service_name, target_group_arn_suffix }, web = { ... } }. Must contain api."
  type = map(object({
    service_name            = string
    target_group_arn_suffix = string
  }))
  validation {
    condition     = contains(keys(var.lb_services), "api")
    error_message = "lb_services must contain api."
  }
}

variable "ecs_services" {
  description = "Every ECS service to watch for CPU and memory (service module `service_names`): { api = \"api\", web = \"web\" }."
  type        = map(string)
}

variable "db_instance_identifier" {
  description = "RDS instance identifier."
  type        = string
}

variable "db_max_connections" {
  description = "Connection ceiling the alarm measures against."
  type        = number
  default     = 200
}

variable "cache_replication_group_id" {
  description = "ElastiCache replication group id; nodes are <id>-001, <id>-002, ..."
  type        = string
}

variable "cache_node_count" {
  description = "Nodes in the replication group (cache module num_cache_clusters)."
  type        = number
  default     = 1
}

variable "target_5xx_threshold" {
  description = "5xx responses per 5 minutes (per app, and at the load balancer) that raise an alarm."
  type        = number
  default     = 25
}

variable "api_p95_latency_seconds" {
  description = "api p95 time to first byte that raises an alarm (scan and protect calls are the hot path)."
  type        = number
  default     = 2
}

variable "scan_completed_log_pattern" {
  description = "CloudWatch Logs JSON filter matching the api's line for a completed scan/mask/redact/tokenize call."
  type        = string
  default     = "{ $.msg = \"scan completed\" }"
}

variable "scan_error_log_pattern" {
  description = "CloudWatch Logs JSON filter matching a failed scan, protect or document call."
  type        = string
  default     = "{ $.msg = \"scan error\" }"
}

variable "review_queued_log_pattern" {
  description = "CloudWatch Logs JSON filter matching a finding sent to the review queue for being below the confidence threshold."
  type        = string
  default     = "{ $.msg = \"finding queued for review\" }"
}

variable "detokenize_denied_log_pattern" {
  description = "CloudWatch Logs JSON filter matching a detokenize call refused for missing the vault-access permission."
  type        = string
  default     = "{ $.msg = \"detokenize denied\" }"
}

variable "scan_error_threshold" {
  description = "Scan/protect errors per 5 minutes that raise an alarm."
  type        = number
  default     = 100
}

variable "detokenize_denied_threshold" {
  description = "Denied detokenize calls per 5 minutes that raise an alarm."
  type        = number
  default     = 20
}

variable "sns_kms_key_arn" {
  description = "CMK for the alarm topic (its key policy must let CloudWatch use it, as the kms module's does)."
  type        = string
}
