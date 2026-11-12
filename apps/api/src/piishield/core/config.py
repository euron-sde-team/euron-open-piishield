"""Runtime configuration, validated once at boot.

Every setting comes from the environment. The API, the CLI and tests all read
``Settings``. Per-project choices (required categories, masking method per category,
confidence threshold, retention) live in the database and are edited through the policies
API; the environment only sets deployment-wide defaults and limits.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

INSECURE_SECRETS = {"", "change-me", "replace-with-output-of-make-env", "dev", "secret"}


def _insecure(value: str) -> bool:
    return value in INSECURE_SECRETS or "not-for-production" in value or len(value) < 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    # Accepted for parity with the deployment's env contract (deploy/compose/compose.yaml);
    # 0.1.0's app code has no cloud-specific branches (boto3/aioboto3 would read
    # AWS_ENDPOINT_URL the same way regardless), so this is informational only today.
    piishield_cloud: Literal["local", "floci", "aws"] = "local"

    database_url: str = "postgresql+asyncpg://piishield:piishield@localhost:5542/piishield"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Policy snapshot cache, tokenization scope maps, review/report rollup caches. Without
    # it each process keeps its own in-memory cache, which is correct for a single replica.
    redis_url: str = ""
    memory_cache_max_bytes: int = Field(64_000_000, ge=1_000_000)

    session_secret: str = "dev-session-secret-not-for-production"  # noqa: S105 dev default
    # Peppers the HMAC of API key secrets. Env name matches the deployment's secret
    # generator (scripts/gen-local-env.sh writes API_KEY_PEPPER).
    api_key_pepper: str = Field("dev-token-pepper-not-for-production", alias="API_KEY_PEPPER")

    # The vault's envelope encryption key: local (a key file, or this literal env value in
    # dev) or KMS. Vault rows are AES-GCM encrypted with a per-record data key wrapped by
    # this master key, so a leaked database alone never recovers a tokenized value.
    key_mode: Literal["local", "kms"] = "local"
    local_master_key: str = "dev-local-master-key-not-for-production-use-only"
    kms_key_id: str = "alias/piishield-local"
    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None
    aws_secrets_enabled: bool = False

    # NoDecode: CORS_ORIGINS arrives as a comma-separated env string (see
    # deploy/compose/compose.yaml), not JSON, which pydantic-settings otherwise requires
    # for a list field; the validator below does the actual splitting.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5510"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    public_url: str = "http://localhost:5510"
    public_api_url: str = "http://localhost:5530"
    signup_enabled: bool = True
    cookie_secure: bool = False

    # The mock AI/LLM service used by the AI gateway's restore flow in demo and tests.
    mock_ai_url: str = Field("http://localhost:5550", alias="MOCK_AI_URL")
    # `piishield seed-demo`'s own HTTP client reaches the API over this address (the
    # Compose network's in-container name/port, not the host-mapped port the browser uses).
    piishield_api_url: str = "http://localhost:8080"

    # Review queue / scan report notifications. 0.1.0 does not send any yet (the review
    # queue and reports are pull, not push); accepted so the container boots against the
    # deployment's env contract without erroring on an unknown var, and so this is the one
    # place a future notifier would read from.
    mail_backend: Literal["log", "smtp", "ses"] = "log"
    mail_from_address: str = "piishield@piishield.local"
    smtp_host: str = "localhost"
    smtp_port: int = Field(1025, ge=1, le=65535)

    # Document exports are request-scoped in 0.1.0 (returned directly in the response,
    # never written to disk; see documents.service), so these are accepted but unused.
    storage: Literal["local", "s3"] = "local"
    local_storage_dir: str = "/data/exports"

    # `make demo`'s printed login; must match scripts/gen-local-env.sh's default.
    piishield_demo_password: str = Field("Demo-Owner-Pass-1", alias="PIISHIELD_DEMO_PASSWORD")

    # Policy cache: in-process TTL, refreshed on every admin write by bumping the version
    # stamp in Redis (or in-process memory without Redis).
    policy_cache_ttl_s: float = Field(5.0, gt=0, le=60)
    # Tokenization scope map TTL in Redis/memory; the durable record is the vault table.
    tokenize_scope_ttl_s: int = Field(3600, ge=60, le=86_400)

    # Default confidence threshold for a project that has not set its own.
    default_confidence_threshold: float = Field(0.6, ge=0.0, le=1.0)

    max_body_bytes: int = Field(25_000_000, ge=10_000)
    max_scan_chars: int = Field(2_000_000, ge=1_000)

    def guard(self) -> None:
        """Refuse to boot in production with demo secrets."""
        if self.environment != "production":
            return
        problems: list[str] = []
        for name in ("api_key_pepper", "session_secret"):
            if _insecure(getattr(self, name)):
                problems.append(f"{name.upper()} must be a random value of at least 32 chars")
        if self.key_mode == "local" and _insecure(self.local_master_key):
            problems.append("LOCAL_MASTER_KEY must be set (or use KEY_MODE=kms)")
        if "*" in self.cors_origins:
            problems.append("CORS_ORIGINS must list the dashboard's origins, not *")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true in production")
        if problems:
            raise RuntimeError("unsafe production configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.guard()
    return settings
