output "secret_arn" {
  description = "ARN of the JSON secret holding SESSION_SECRET, API_KEY_PEPPER and (with include_connection_urls) DATABASE_URL and REDIS_URL."
  value       = aws_secretsmanager_secret.app.arn
}

output "bootstrap_secret_arn" {
  description = "ARN of the JSON secret holding PIISHIELD_ADMIN_PASSWORD (scripts/aws-run-task.sh writes and scrubs it)."
  value       = aws_secretsmanager_secret.bootstrap.arn
}

output "keys" {
  description = "Every environment variable the secrets provide to api and migrate."
  value       = sort(local.app_keys)
}

output "ecs_secrets" {
  description = "ECS `secrets` entries for api and migrate: [{ name, valueFrom = \"<arn>:<key>::\" }]."
  value       = local.ecs_secrets
}

output "bootstrap_secrets" {
  description = "ECS `secrets` entries for the migrate task only (PIISHIELD_ADMIN_PASSWORD)."
  value       = local.bootstrap_secrets
}
