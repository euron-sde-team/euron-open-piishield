# Configuration

Every runtime setting comes from the environment and is validated once at boot by
`Settings` (`apps/api/src/piishield/core/config.py`). Per-project choices (required
categories, masking method per category, confidence threshold, retention) are not
environment configuration at all: they live in the database and are edited through the
Policies API/dashboard, see [walkthrough.md](walkthrough.md). This page documents every
field `Settings` accepts and the matching `deploy/compose/.env` variable where one exists.

`make env` generates `deploy/compose/.env` for local use with random secrets; it is
gitignored, and this is the one file an operator edits for a local deployment.

## Core

| Setting | Env var | Default | Notes |
| --- | --- | --- | --- |
| `environment` | `ENVIRONMENT` | `development` | `development`, `test`, or `production`. `production` triggers the boot guard below. |
| `log_level` | `LOG_LEVEL` | `INFO` | |
| `piishield_cloud` | `PIISHIELD_CLOUD` | `local` | `local`, `floci`, or `aws`. Informational only in 0.1.0: app code has no cloud-specific branch, since boto3/aioboto3 read `AWS_ENDPOINT_URL` the same way regardless of this value. |
| `database_url` | `DATABASE_URL` | `postgresql+asyncpg://piishield:piishield@localhost:5542/piishield` | |
| `db_pool_size` / `db_max_overflow` | `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `10` / `20` | |

## Cache and KV

| Setting | Env var | Default | Notes |
| --- | --- | --- | --- |
| `redis_url` | `REDIS_URL` | empty | Without it, the policy cache and tokenization scope map fall back to in-process memory (`MemoryKV`), correct for a single replica. With it, state is shared cluster-wide. See [HLD.md](../architecture/HLD.md)'s caching table. |
| `memory_cache_max_bytes` | `MEMORY_CACHE_MAX_BYTES` | 64,000,000 | Bound on the in-process fallback cache's size. |
| `policy_cache_ttl_s` | `POLICY_CACHE_TTL_S` | `5.0` (1 to 60) | The policy snapshot cache's TTL; see [ADR-0002](../architecture/adr/0002-bounded-staleness-policy-cache.md). |
| `tokenize_scope_ttl_s` | `TOKENIZE_SCOPE_TTL_S` | `3600` (60 to 86400) | The tokenization scope map's TTL in KV; the durable record is always the vault table, so this only affects the speed of a repeat lookup, never correctness. |

## Secrets and the vault

| Setting | Env var | Default | Notes |
| --- | --- | --- | --- |
| `session_secret` | `SESSION_SECRET` | dev placeholder | Signs dashboard sessions. |
| `api_key_pepper` | `API_KEY_PEPPER` | dev placeholder | Peppers the HMAC of every project API key's secret half; never stored in the clear. |
| `key_mode` | `KEY_MODE` | `local` | `local` or `kms`. **`kms` is not implemented in 0.1.0**: `build_sealer` raises `NotImplementedError` at boot rather than silently falling back to `local`. Use `key_mode=local` for every 0.1.0 deployment. See [ADR-0001](../architecture/adr/0001-envelope-encryption-local-key-only.md). |
| `local_master_key` | `LOCAL_MASTER_KEY` | dev placeholder | The vault's AES-256-GCM key source when `key_mode=local` (hashed with SHA-256 to get exactly 32 bytes). This is the single most sensitive value in a PIIShield deployment: anyone with it and the database can decrypt every vault entry. |
| `kms_key_id` | `KMS_KEY_ID` | `alias/piishield-local` | Accepted so the container boots against the deployment's full env contract; has no effect while `key_mode=kms` is unimplemented. |

## Networking

| Setting | Env var | Default | Notes |
| --- | --- | --- | --- |
| `aws_region` | `AWS_REGION` | `us-east-1` | |
| `aws_endpoint_url` | `AWS_ENDPOINT_URL` | unset | Set to Floci's address locally; boto3/aioboto3 read it directly. |
| `aws_secrets_enabled` | `AWS_SECRETS_ENABLED` | `false` | **Accepted but unused in 0.1.0**: there is no Secrets Manager read path in the app code yet. Nothing should be assumed enabled because this flag is set. |
| `cors_origins` | `CORS_ORIGINS` | `http://localhost:5510` | Comma-separated (not JSON) in the environment; split by a field validator. Must not be `*` in production (boot guard). |
| `public_url` / `public_api_url` | `PUBLIC_URL` / `PUBLIC_API_URL` | `http://localhost:5510` / `:5530` | |
| `cookie_secure` | `COOKIE_SECURE` | `false` | Must be `true` in production (boot guard). |

## Mail

| Setting | Env var | Default | Notes |
| --- | --- | --- | --- |
| `mail_backend` | `MAIL_BACKEND` | `log` | `log`, `smtp`, or `ses`. Compose's Floci overlay defaults to `smtp` (Mailpit) so a fresh `make up` shows mail without first verifying a sender identity in the SES sandbox; set `PS_MAIL_BACKEND=ses` to exercise the real SES identity Terraform provisions on Floci instead. |
| `mail_from_address` | `MAIL_FROM_ADDRESS` | `piishield@piishield.local` | |
| `smtp_host` / `smtp_port` | `SMTP_HOST` / `SMTP_PORT` | `localhost` / `1025` | Mailpit's SMTP port locally. |

0.1.0 does not send any mail yet; the review queue and reports are pull-based, read by
visiting the dashboard, not pushed. These settings exist so the container boots against
the deployment's full env contract and so a future notifier has an established place to
read from.

## Documents

| Setting | Env var | Default | Notes |
| --- | --- | --- | --- |
| `storage` | `STORAGE` | `local` | `local` or `s3`. **Accepted but unused in 0.1.0**: document protection is request-scoped (the protected file is returned directly in the HTTP response, never written to disk or S3, see `documents/service.py`). |
| `local_storage_dir` | `LOCAL_STORAGE_DIR` | `/data/exports` | Unused for the same reason. |

## Detection and limits

| Setting | Env var | Default | Notes |
| --- | --- | --- | --- |
| `default_confidence_threshold` | `DEFAULT_CONFIDENCE_THRESHOLD` | `0.6` | Used for a project that has not set its own policy. |
| `max_body_bytes` | `MAX_BODY_BYTES` | 25,000,000 | Request body size cap. |
| `max_scan_chars` | `MAX_SCAN_CHARS` | 2,000,000 | A single scan never processes more than this many characters of input text. |

## Demo

| Setting | Env var | Default | Notes |
| --- | --- | --- | --- |
| `piishield_demo_password` | `PIISHIELD_DEMO_PASSWORD` | `Demo-Owner-Pass-1` | Must match `scripts/gen-local-env.sh`'s own default or `make demo`/`make e2e`/`make qa` disagree on the password. A published demo value, not a secret. |
| `mock_ai_url` | `MOCK_AI_URL` | `http://localhost:5550` | The AI gateway's `restore` flow target in demo and tests. |

## Local ports (`deploy/compose/.env`, `PS_*` prefix)

| Variable | Default |
| --- | --- |
| `PS_WEB_PORT` | 5510 |
| `PS_API_PORT` | 5530 |
| `PS_PG_PORT` | 5542 |
| `PS_REDIS_PORT` | 5579 |
| `PS_FLOCI_PORT` | 5566 |
| `PS_MAILPIT_PORT` | 5525 |
| `PS_SMTP_PORT` | 5526 |
| `PS_MOCK_AI_PORT` | 5550 |

All bound to `127.0.0.1` only. Never 3000, 3001, 5060, 4040 or 8081, reserved by other
work on this program.

## Production boot guard

`Settings.guard()` runs once at startup and, only when `environment=production`, refuses
to boot with:

- `API_KEY_PEPPER` or `SESSION_SECRET` under 32 characters, or a known insecure default
  (`""`, `"change-me"`, `"dev"`, `"secret"`, `"replace-with-output-of-make-env"`, or
  containing `"not-for-production"`).
- `key_mode=local` with an equally insecure `LOCAL_MASTER_KEY` (the same rule; `key_mode=
  kms` is not a way around this guard, it simply is not implemented at all in 0.1.0).
- `CORS_ORIGINS` containing `"*"`.
- `COOKIE_SECURE` not `true`.

Every problem found is listed in one `RuntimeError`, so a misconfigured production
deployment fails at boot with a complete list rather than one error at a time.
