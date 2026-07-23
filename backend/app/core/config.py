from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
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

    stripe_client_id: str = ""
    stripe_client_secret: str = ""
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_api_url: str = "https://api-m.sandbox.paypal.com"
    paypal_authorize_url: str = "https://www.sandbox.paypal.com/signin/authorize"
    razorpay_client_id: str = ""
    razorpay_client_secret: str = ""
    razorpay_oauth_mode: Literal["test", "live"] = "test"
    cashfree_oauth_client_id: str = ""
    cashfree_partner_api_key: str = ""
    cashfree_api_url: str = "https://api-sandbox.cashfree.com"
    cashfree_payments_url: str = "https://sandbox.cashfree.com"

    dodo_payments_api_key: str = ""
    dodo_payments_api_url: str = "https://test.dodopayments.com"
    dodo_payments_product_id: str = ""
    billing_cron_secret: str = "development-billing-cron-secret"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
