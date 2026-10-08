"""Provider-agnostic payment and payout abstractions.

The platform collects every invitee payment on its own account and splits it
with the host through a payout provider (Razorpay Route today). New providers
plug in by implementing ``PaymentGateway`` and registering in
``get_payment_gateway``.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.domains.payments.models import BusinessType, PaymentProvider


class ProviderAPIError(RuntimeError):
    """A payment provider rejected a request or could not be reached."""

    def __init__(self, message: str, *, code: str | None = None, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.field = field
        # Provider ids created before the failure, so onboarding can resume later.
        self.partial_state: "LinkedAccountState | None" = None


@dataclass(frozen=True)
class Address:
    street1: str
    street2: str | None
    city: str
    state: str
    postal_code: str
    country: str = "IN"


@dataclass(frozen=True)
class HostPayoutProfile:
    """Everything a payout provider needs to onboard a host's bank account."""

    reference_id: str
    email: str
    phone: str
    contact_name: str
    legal_business_name: str
    business_type: BusinessType
    category: str
    subcategory: str
    address: Address
    pan: str | None
    account_number: str
    ifsc_code: str
    beneficiary_name: str


@dataclass(frozen=True)
class PayoutRequirement:
    field_reference: str
    reason_code: str
    status: str
    description: str | None = None


@dataclass(frozen=True)
class LinkedAccountState:
    linked_account_id: str | None
    stakeholder_id: str | None
    product_configuration_id: str | None
    activation_status: str
    requirements: list[PayoutRequirement] = field(default_factory=list)


@dataclass(frozen=True)
class OrderTransfer:
    destination_account_id: str
    amount_minor: int
    currency: str
    notes: dict[str, str]


@dataclass(frozen=True)
class OrderRequest:
    amount_minor: int
    currency: str
    receipt: str
    notes: dict[str, str]
    transfers: list[OrderTransfer]


@dataclass(frozen=True)
class Order:
    order_id: str
    amount_minor: int
    currency: str


@dataclass(frozen=True)
class Refund:
    refund_id: str
    status: str


@dataclass(frozen=True)
class GatewayEvent:
    """A normalized provider webhook event."""

    event_id: str
    event_type: str
    # Payment captured / order paid.
    payment_id: str | None = None
    order_id: str | None = None
    amount_minor: int | None = None
    booking_id: str | None = None
    # Linked account activation updates.
    linked_account_id: str | None = None
    activation_status: str | None = None
    requirements: list[PayoutRequirement] | None = None
    # Refund updates.
    refund_id: str | None = None
    refund_status: str | None = None

    @property
    def is_payment_success(self) -> bool:
        return self.payment_id is not None and self.amount_minor is not None

    @property
    def is_payout_status(self) -> bool:
        return self.linked_account_id is not None and self.activation_status is not None

    @property
    def is_refund_update(self) -> bool:
        return self.refund_id is not None and self.refund_status is not None


class PaymentGateway(ABC):
    """Platform-level gateway: collects payments and routes the host share."""

    provider: PaymentProvider
    public_key: str

    # Payouts (host onboarding)
    @abstractmethod
    def onboard_host(self, profile: HostPayoutProfile, current: LinkedAccountState) -> LinkedAccountState:
        """Create or resume onboarding and return the latest provider state."""

    @abstractmethod
    def update_host(self, profile: HostPayoutProfile, current: LinkedAccountState) -> LinkedAccountState:
        """Push changed host details (including bank account) to the provider."""

    @abstractmethod
    def fetch_host_status(self, current: LinkedAccountState) -> LinkedAccountState:
        """Refresh the activation status of an onboarded host."""

    # Collections
    @abstractmethod
    def create_order(self, request: OrderRequest) -> Order:
        raise NotImplementedError

    @abstractmethod
    def verify_checkout_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def verify_webhook(self, body: bytes, headers: dict[str, str]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> GatewayEvent | None:
        raise NotImplementedError

    @abstractmethod
    def refund(self, payment_id: str, amount_minor: int, *, reverse_transfers: bool, notes: dict[str, str]) -> Refund:
        raise NotImplementedError


def get_payment_gateway() -> PaymentGateway | None:
    """Return the configured platform gateway, or None when payments are not configured."""
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        return None
    from app.domains.payments.razorpay_route import RazorpayRouteGateway

    return RazorpayRouteGateway(
        key_id=settings.razorpay_key_id,
        key_secret=settings.razorpay_key_secret,
        webhook_secret=settings.razorpay_webhook_secret,
        api_url=settings.razorpay_api_url,
    )
