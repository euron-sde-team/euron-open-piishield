# PIIShield's own secrets, in Secrets Manager. ECS injects each JSON key into the
# containers that need it as an environment variable; the values never appear in a task
# definition, a plan diff or a log. Each consumer gets only its own keys (see the outputs).
#
# Two secrets with different lifecycles and readers:
#
#   <name_prefix>/app           SESSION_SECRET, API_KEY_PEPPER and LOCAL_MASTER_KEY. Read
#                               by the api and the migrate task. API_KEY_PEPPER peppers
#                               the hashes of project API keys (psk_<prefix>_<secret>).
#                               LOCAL_MASTER_KEY seals the vault's envelope encryption
#                               under KEY_MODE=local, 0.1.0's only shipped key backend
#                               (core/sealing.py raises NotImplementedError for
#                               key_mode=kms on purpose; see
#                               docs/architecture/adr/0001-envelope-encryption-local-key-only.md).
#                               Locally (Compose) the equivalent value comes from
#                               deploy/compose/.env instead of this module.
#   <name_prefix>/bootstrap     PIISHIELD_ADMIN_PASSWORD, read only by the one-off
#                               migrate task: `make aws-admin` puts the first owner's
#                               password here, runs `create-admin`, then overwrites it
#                               with a random value. The password never travels as an ECS
#                               task override (those stay readable to anyone allowed to
#                               describe the task).
#
# DATABASE_URL and REDIS_URL are generated once by the database and cache modules and
# merged into the app secret here (include_connection_urls) so the api and migrate tasks
# read one JSON document for every connection string they need.
#
# Generated once, then rotated out of band; Terraform never rolls them back. Locally
# (Compose) the same values come from deploy/compose/.env.
locals {
  app_keys = concat(
    ["SESSION_SECRET", "API_KEY_PEPPER", "LOCAL_MASTER_KEY"],
    var.include_connection_urls ? ["DATABASE_URL", "REDIS_URL"] : [],
  )
}

resource "random_password" "this" {
  for_each = toset(["SESSION_SECRET", "API_KEY_PEPPER", "LOCAL_MASTER_KEY", "PIISHIELD_ADMIN_PASSWORD"])
  length   = 64
  special  = false
}

resource "aws_secretsmanager_secret" "app" {
  #checkov:skip=CKV2_AWS_57:A session signing key, an API key pepper and the vault's master key (plus the generated connection URLs); rotation is an operator procedure (docs/guides/operations.md), not a Lambda.
  name                    = "${var.name_prefix}/app"
  description             = "PIIShield signing secrets (session, API key pepper, vault master key) and connection URLs"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = var.recovery_window_in_days
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode(merge(
    { for k in ["SESSION_SECRET", "API_KEY_PEPPER", "LOCAL_MASTER_KEY"] : k => random_password.this[k].result },
    var.include_connection_urls ? { DATABASE_URL = var.database_url, REDIS_URL = var.redis_url } : {},
  ))

  # Rotation happens out of band (put a new version by hand or by pipeline). Without
  # this, the next `terraform apply` would quietly roll every secret back.
  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "bootstrap" {
  #checkov:skip=CKV2_AWS_57:Holds a random placeholder except for the seconds `make aws-admin` runs create-admin; nothing to rotate.
  name                    = "${var.name_prefix}/bootstrap"
  description             = "PIIShield first-owner password for the one-off create-admin task (random placeholder otherwise)"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = var.recovery_window_in_days
}

resource "aws_secretsmanager_secret_version" "bootstrap" {
  secret_id     = aws_secretsmanager_secret.bootstrap.id
  secret_string = jsonencode({ PIISHIELD_ADMIN_PASSWORD = random_password.this["PIISHIELD_ADMIN_PASSWORD"].result })

  # scripts/aws-run-task.sh writes and then scrubs this value.
  lifecycle {
    ignore_changes = [secret_string]
  }
}

locals {
  # api and migrate.
  ecs_secrets = [for k in local.app_keys : { name = k, valueFrom = "${aws_secretsmanager_secret.app.arn}:${k}::" }]
  # The migrate task only.
  bootstrap_secrets = [
    { name = "PIISHIELD_ADMIN_PASSWORD", valueFrom = "${aws_secretsmanager_secret.bootstrap.arn}:PIISHIELD_ADMIN_PASSWORD::" },
  ]
}
