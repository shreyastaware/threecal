from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Threecal API"
    environment: Literal["development", "test", "production"] = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./threecal.db"
    auto_create_tables: bool = True

    jwt_secret_key: str = "development-only-change-this-secret-before-deploying"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    auth_cookie_name: str = "threecal_access_token"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    auth_cookie_domain: str | None = None
    # Single-use tokens emailed for account recovery and email ownership checks.
    email_verification_token_ttl_hours: int = 48
    password_reset_token_ttl_minutes: int = 60

    # Abuse protection. Only trust X-Forwarded-For behind a known proxy (Railway).
    rate_limit_enabled: bool = True
    rate_limit_backend: Literal["memory"] = "memory"
    trust_proxy_headers: bool = False

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    email_provider: Literal["console", "smtp"] = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "bookings@threecal.com"
    smtp_use_tls: bool = True
    webhook_secret: str = "development-webhook-secret"

    credentials_encryption_key: str = "development-only-payment-credentials-key"
    public_api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_base_url: str = ""

    # Observability: Sentry error tracking (disabled when SENTRY_DSN is empty).
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0
    sentry_environment: str = ""
    sentry_release: str = ""

    # Logging: JSON logs to stdout, optionally pushed to Grafana Loki.
    log_level: str = "INFO"
    loki_url: str = ""
    loki_username: str = ""
    loki_password: str = ""

    # Database backups to Cloudflare R2 (falls back to R2_BUCKET_NAME).
    backup_r2_bucket_name: str = ""
    backup_prefix: str = "backups/"
    backup_retention_days: int = 30
    backup_hour_utc: int = Field(default=3, ge=0, le=23)

    # In-process job scheduler (expire pending bookings, daily backups). Enable on the single API instance.
    scheduler_enabled: bool = False
    expire_pending_bookings_interval_minutes: int = Field(default=5, ge=1)

    # Booking notifications. Invitees may cancel/reschedule until this many hours before the start.
    invitee_change_cutoff_hours: int = Field(default=24, ge=0)
    # Reminder emails, in minutes before the start (comma-separated in the environment).
    reminder_offsets_minutes: Annotated[list[int], NoDecode] = [1440, 60]
    send_booking_reminders_interval_minutes: int = Field(default=5, ge=1)
    # A reminder whose send time passed more than this long ago is skipped (never sent late).
    reminder_grace_minutes: int = Field(default=30, ge=1)

    # Invitees pay into the platform Razorpay account; Route splits each payment
    # between the platform commission and the host's linked account.
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_api_url: str = "https://api.razorpay.com"
    # Platform commission in basis points (100 = 1%).
    platform_commission_bps: int = Field(default=0, ge=0, le=10_000)

    # Calendar and conferencing integrations (OAuth apps). Endpoints return 503 when unset.
    google_client_id: str = ""
    google_client_secret: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant: str = "common"
    zoom_client_id: str = ""
    zoom_client_secret: str = ""
    # How long busy times from connected calendars are cached per host and range.
    calendar_busy_cache_seconds: int = Field(default=60, ge=0)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("reminder_offsets_minutes", mode="before")
    @classmethod
    def parse_reminder_offsets(cls, value: object) -> object:
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        return value

    @field_validator("reminder_offsets_minutes")
    @classmethod
    def validate_reminder_offsets(cls, value: list[int]) -> list[int]:
        if any(offset <= 0 for offset in value):
            raise ValueError("Reminder offsets must be positive minutes.")
        # Largest first, without duplicates.
        return sorted(set(value), reverse=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
