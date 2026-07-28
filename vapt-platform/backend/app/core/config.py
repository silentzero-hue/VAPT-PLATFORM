"""Application configuration loaded from environment."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Disallowed values for `jwt_algorithm`. Pin to a Literal at the call sites.
JWT_ALLOWED_ALGS: tuple[str, ...] = ("HS256", "HS384", "HS512", "RS256", "RS384", "RS512")


class Settings(BaseSettings):
    # Look for .env in the current working directory and one level up (project
    # root). This handles both `uvicorn app.main:app` from `backend/` AND
    # pytest from the project root.
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "VAPT Platform"
    app_env: Literal["development", "staging", "production"] = "development"
    app_log_level: str = "info"
    app_timezone: str = "UTC"
    api_v1_prefix: str = "/api/v1"

    database_url: str
    redis_url: str

    s3_endpoint: str
    s3_public_endpoint: str
    s3_region: str = "us-east-1"
    s3_bucket: str
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    minio_root_user: str = "vapt"
    # No default — startup fails loudly if unset, instead of running with a known-bad credential.
    minio_root_password: str

    # JWT
    jwt_secret: str
    # Pin to allowed algorithms. Use Literal on consumer side; reject "none", empty, etc.
    jwt_algorithm: Literal["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"] = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 7
    totp_issuer: str = "VAPT-Platform"
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    # OWASP recommends parallelism=1 for server use; tune time_cost if more work needed.
    argon2_parallelism: int = 1

    # Data encryption (TOTP secrets, LDAP bind passwords, Nessus creds).
    # MUST be a real Fernet key (base64url-encoded 32 bytes), independent of jwt_secret.
    data_encryption_key: str

    # Lockout: per-account counters.
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    login_totp_max_attempts: int = 5
    login_totp_lockout_minutes: int = 15

    llm_provider: Literal["anthropic", "openai", "local"] = "anthropic"
    llm_api_key: str
    llm_model: str = "claude-sonnet-4-5"
    llm_base_url: str | None = None
    llm_max_tokens: int = 8192
    llm_temperature: float = 0.2

    mcp_server_url: str = "http://mcp:8081"

    ingestion_poll_interval_sec: int = 60
    ingestion_drop_path: str = "/var/ingest"

    backup_path: str = "/var/backups/vapt"
    backup_retention_days: int = 30

    # DOCX report template. Path is resolved relative to CWD; the bundled
    # default ships under app/services/reporting/templates/.
    report_template_path: str = "app/services/reporting/templates/dmc_vapt_report.docx"
    # Company name used to replace the DMC template's hardcoded "Technovage
    # Solution" string in the Methodology paragraph. Empty falls back to a
    # generic phrase so we never leak the template's branding into a new
    # client's report. The disclaimer is left untouched.
    report_company_name: str = ""

    # Per-endpoint rate limits (applied via @limiter.limit)
    rate_limit_default: str = "200/minute"
    rate_limit_login: str = "10/minute"
    rate_limit_totp: str = "5/minute"
    rate_limit_refresh: str = "60/minute"
    rate_limit_ingest: str = "30/minute"
    rate_limit_agent: str = "10/minute"
    rate_limit_portal: str = "30/minute"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    @field_validator("minio_root_password")
    @classmethod
    def _no_placeholder_minio_password(cls, v: str) -> str:
        # If we are about to ship the platform with `changeme` or empty password, fail.
        # Compare case-insensitively to catch common typos.
        if v.strip().lower() in {"", "changeme", "change-me", "password"}:
            raise ValueError(
                "minio_root_password must be set to a non-default value; see .env"
            )
        return v

    @field_validator("data_encryption_key")
    @classmethod
    def _encryption_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("data_encryption_key must be at least 32 characters")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
