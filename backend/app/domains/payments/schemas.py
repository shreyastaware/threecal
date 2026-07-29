from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.domains.payments.models import BusinessType, PaymentProvider


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
    public_key: str | None = None


Currency = Annotated[str, Field(min_length=3, max_length=3)]


class PaymentAccountBase(BaseModel):
    account_name: str = Field(min_length=2, max_length=120)
    account_email: EmailStr
    business_type: BusinessType
    business_name: str = Field(min_length=2, max_length=160)
    branch_ifsc_code: str = Field(pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$")
    beneficiary_name: str = Field(min_length=2, max_length=120)

    @field_validator(
        "account_name",
        "business_name",
        "beneficiary_name",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("branch_ifsc_code", mode="before")
    @classmethod
    def normalize_ifsc_code(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class PaymentAccountCreate(PaymentAccountBase):
    account_number: SecretStr

    @field_validator("account_number")
    @classmethod
    def validate_account_number(cls, value: SecretStr) -> SecretStr:
        account_number = value.get_secret_value()
        if not 6 <= len(account_number) <= 34 or not account_number.isdigit():
            raise ValueError("Account number must contain 6 to 34 digits")
        return value


class PaymentAccountUpdate(PaymentAccountBase):
    account_number: SecretStr | None = None

    @field_validator("account_number")
    @classmethod
    def validate_account_number(
        cls,
        value: SecretStr | None,
    ) -> SecretStr | None:
        if value is None:
            return value
        account_number = value.get_secret_value()
        if not 6 <= len(account_number) <= 34 or not account_number.isdigit():
            raise ValueError("Account number must contain 6 to 34 digits")
        return value


class PaymentAccountRead(PaymentAccountBase):
    model_config = ConfigDict(from_attributes=True)

    masked_account_number: str
