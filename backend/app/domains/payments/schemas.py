from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from app.domains.payments.models import PaymentProvider


class CredentialConnectRequest(BaseModel):
    provider: PaymentProvider
    api_key: SecretStr
    secret_key: SecretStr | None = None
    account_id: str | None = Field(default=None, max_length=2048)
    store_url: str | None = Field(default=None, max_length=2048, pattern=r"^https?://")
    store_id: str | None = Field(default=None, max_length=255)
    webhook_secret: SecretStr | None = None

    @model_validator(mode="after")
    def disallow_oauth_providers(self) -> "CredentialConnectRequest":
        if self.provider in {PaymentProvider.STRIPE, PaymentProvider.PAYPAL}:
            raise ValueError("Stripe and PayPal must be connected with OAuth.")
        if self.provider in {PaymentProvider.RAZORPAY, PaymentProvider.CASHFREE} and not self.secret_key:
            raise ValueError("This provider requires both key fields.")
        if self.provider == PaymentProvider.BTCPAY and (not self.store_url or not self.store_id):
            raise ValueError("BTCPay requires a store URL and store ID.")
        return self


class PaymentConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    provider: PaymentProvider
    account_id: str | None
    connected: bool = True


class OAuthStartRead(BaseModel):
    authorization_url: str


class CheckoutRead(BaseModel):
    provider: PaymentProvider
    provider_payment_id: str
    client_secret: str | None = None
    checkout_url: str | None = None


Currency = Annotated[str, Field(min_length=3, max_length=3)]
