import re
import uuid
from typing import Annotated

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.domains.bookings.models import BookingStatus
from app.domains.payments.categories import BUSINESS_CATEGORIES
from app.domains.payments.models import BusinessType, LinkedAccountStatus, PaymentProvider


Currency = Annotated[str, Field(min_length=3, max_length=3)]

PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
# Razorpay: an owner's personal PAN has "P" as its 4th character; business PANs use these.
BUSINESS_PAN_HOLDER_TYPES = set("CHFATBJGL")
PERSONAL_PAN_BUSINESS_TYPES = {
    BusinessType.INDIVIDUAL,
    BusinessType.NOT_YET_REGISTERED,
    BusinessType.PROPRIETORSHIP,
}


def _validate_pan(value: SecretStr | None) -> SecretStr | None:
    if value is None:
        return value
    pan = value.get_secret_value().strip().upper()
    if not PAN_PATTERN.match(pan):
        raise ValueError("PAN must look like ABCDE1234F")
    return SecretStr(pan)


def _validate_account_number(value: SecretStr | None) -> SecretStr | None:
    if value is None:
        return value
    account_number = value.get_secret_value()
    if not 6 <= len(account_number) <= 34 or not account_number.isdigit():
        raise ValueError("Account number must contain 6 to 34 digits")
    return value


class PaymentAccountBase(BaseModel):
    account_name: str = Field(min_length=2, max_length=120)
    account_email: EmailStr
    business_type: BusinessType
    business_name: str = Field(min_length=4, max_length=160)
    branch_ifsc_code: str = Field(pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$")
    beneficiary_name: str = Field(min_length=2, max_length=120)
    # Additional details Razorpay Route needs to create the linked account.
    phone: str = Field(pattern=r"^[0-9]{8,15}$")
    business_category: str = Field(min_length=2, max_length=64)
    business_subcategory: str = Field(min_length=2, max_length=64)
    street1: str = Field(min_length=3, max_length=100)
    street2: str | None = Field(default=None, max_length=100)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=32)
    postal_code: str = Field(pattern=r"^[1-9][0-9]{5}$")

    @field_validator(
        "account_name",
        "business_name",
        "beneficiary_name",
        "street1",
        "city",
        "state",
        "postal_code",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("street2", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: object) -> object:
        return re.sub(r"[\s()+-]", "", value) if isinstance(value, str) else value

    @field_validator("branch_ifsc_code", mode="before")
    @classmethod
    def normalize_ifsc_code(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_category(self) -> "PaymentAccountBase":
        subcategories = BUSINESS_CATEGORIES.get(self.business_category)
        if subcategories is None:
            raise ValueError("Choose a supported business category")
        if self.business_subcategory not in subcategories:
            raise ValueError("Choose a sub-category that belongs to the business category")
        return self

    def check_pan_matches_business_type(self, pan: SecretStr | None) -> None:
        if pan is None:
            return
        holder_type = pan.get_secret_value()[3]
        if self.business_type in PERSONAL_PAN_BUSINESS_TYPES:
            if holder_type != "P":
                raise ValueError("Enter the owner's personal PAN (4th character P) for this business type")
        elif holder_type not in BUSINESS_PAN_HOLDER_TYPES:
            raise ValueError("Enter the business PAN for this business type")


class PaymentAccountCreate(PaymentAccountBase):
    account_number: SecretStr
    pan: SecretStr

    @field_validator("account_number")
    @classmethod
    def validate_account_number(cls, value: SecretStr) -> SecretStr:
        _validate_account_number(value)
        return value

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, value: SecretStr) -> SecretStr:
        return _validate_pan(value) or value

    @model_validator(mode="after")
    def validate_pan_type(self) -> "PaymentAccountCreate":
        self.check_pan_matches_business_type(self.pan)
        return self


class PaymentAccountUpdate(PaymentAccountBase):
    # Omit to keep the saved value.
    account_number: SecretStr | None = None
    pan: SecretStr | None = None

    @field_validator("account_number")
    @classmethod
    def validate_account_number(
        cls,
        value: SecretStr | None,
    ) -> SecretStr | None:
        return _validate_account_number(value)

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, value: SecretStr | None) -> SecretStr | None:
        return _validate_pan(value)

    @model_validator(mode="after")
    def validate_pan_type(self) -> "PaymentAccountUpdate":
        self.check_pan_matches_business_type(self.pan)
        return self


class PayoutRequirementRead(BaseModel):
    field_reference: str
    reason_code: str
    status: str
    description: str | None = None


class PaymentAccountRead(BaseModel):
    account_name: str
    account_email: str
    business_type: BusinessType
    business_name: str
    branch_ifsc_code: str
    beneficiary_name: str
    masked_account_number: str
    # Nullable for accounts saved before payouts onboarding existed.
    phone: str | None
    business_category: str | None
    business_subcategory: str | None
    street1: str | None
    street2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    masked_pan: str | None
    activation_status: LinkedAccountStatus
    payouts_enabled: bool
    # False when the platform has not configured its payment provider yet.
    payouts_configured: bool
    requirements: list[PayoutRequirementRead]


class CheckoutPrefill(BaseModel):
    name: str
    email: str


class CheckoutRead(BaseModel):
    provider: PaymentProvider
    booking_id: uuid.UUID
    key_id: str
    order_id: str
    amount: int
    currency: str
    name: str
    description: str
    prefill: CheckoutPrefill


class PaymentVerificationRequest(BaseModel):
    razorpay_order_id: str = Field(min_length=1, max_length=255)
    razorpay_payment_id: str = Field(min_length=1, max_length=255)
    razorpay_signature: str = Field(min_length=1, max_length=255)


class PaymentVerificationRead(BaseModel):
    booking_id: uuid.UUID
    status: BookingStatus
