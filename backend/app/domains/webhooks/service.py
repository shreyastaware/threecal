import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from fastapi import status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.billing.models import PlatformBilling
from app.domains.billing.repository import BillingRepository
from app.domains.bookings.models import Booking, BookingStatus
from app.domains.payments.gateways import ProviderAPIError, create_gateway
from app.domains.payments.models import PaymentProvider
from app.domains.payments.repository import PaymentConfigRepository
from app.domains.webhooks.models import WebhookEvent


@dataclass(frozen=True)
class SuccessfulPayment:
    event_id: str
    event_type: str
    booking_id: uuid.UUID
    payment_id: str
    amount_minor: int


class WebhookService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.configs = PaymentConfigRepository(db)

    def process(
        self,
        provider: PaymentProvider,
        doctor_id: uuid.UUID,
        body: bytes,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, str]:
        config = self.configs.get_for_doctor(doctor_id)
        if not config or config.provider != provider:
            raise AppError(status.HTTP_404_NOT_FOUND, "payment_config_not_found", "Payment provider configuration not found.")
        gateway = create_gateway(provider, self.configs.credentials(config), config.account_id)
        try:
            verified = gateway.verify_webhook(body, headers, self.configs.webhook_secret(config))
        except ProviderAPIError as exc:
            raise AppError(502, "webhook_verification_failed", "The provider could not verify this webhook.") from exc
        if not verified:
            raise AppError(status.HTTP_401_UNAUTHORIZED, "invalid_signature", "Invalid webhook signature.")

        payment = extract_successful_payment(provider, payload, headers)
        if not payment:
            return {"status": "ignored"}
        event = WebhookEvent(
            provider=provider.value,
            external_id=payment.event_id,
            event_type=payment.event_type,
            payload=body.decode(),
            status="processed",
        )
        self.db.add(event)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            return {"status": "duplicate"}

        booking = self.db.get(Booking, payment.booking_id)
        if not booking or booking.host_id != doctor_id:
            self.db.rollback()
            raise AppError(404, "booking_not_found", "The webhook booking was not found for this doctor.")
        if booking.status == BookingStatus.CONFIRMED:
            self.db.commit()
            return {"status": "duplicate"}
        if booking.status != BookingStatus.PENDING:
            self.db.rollback()
            raise AppError(409, "booking_not_payable", "The booking cannot be marked paid.")
        if payment.amount_minor != booking.booking_amount:
            self.db.rollback()
            raise AppError(409, "payment_amount_mismatch", "The provider payment amount does not match the booking amount.")
        billing = BillingRepository(self.db).get_for_doctor(doctor_id)
        if not billing:
            self.db.rollback()
            raise AppError(409, "platform_billing_missing", "Platform billing is not configured.")

        booking.status = BookingStatus.CONFIRMED
        booking.provider_payment_id = payment.payment_id
        self.db.execute(
            update(PlatformBilling)
            .where(PlatformBilling.id == billing.id)
            .values(current_cycle_earnings=PlatformBilling.current_cycle_earnings + booking.booking_amount)
        )
        self.db.commit()
        return {"status": "processed"}


def extract_successful_payment(
    provider: PaymentProvider,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> SuccessfulPayment | None:
    try:
        if provider == PaymentProvider.STRIPE:
            event_type = str(payload["type"])
            if event_type != "payment_intent.succeeded":
                return None
            payment = payload["data"]["object"]
            return _result(str(payload["id"]), event_type, payment["metadata"]["booking_id"], payment["id"], int(payment["amount_received"]))
        if provider == PaymentProvider.RAZORPAY:
            event_type = str(payload["event"])
            if event_type != "order.paid":
                return None
            order = payload["payload"]["order"]["entity"]
            return _result(headers.get("x-razorpay-event-id", str(order["id"])), event_type, order["notes"]["booking_id"], order["id"], int(order["amount_paid"]))
        if provider == PaymentProvider.CASHFREE:
            event_type = str(payload["type"])
            if event_type != "PAYMENT_SUCCESS_WEBHOOK":
                return None
            data = payload["data"]
            return _result(headers.get("x-idempotency-key", str(data["payment"]["cf_payment_id"])), event_type, data["order"]["order_id"], data["payment"]["cf_payment_id"], _major_to_minor(data["payment"]["payment_amount"]))
        if provider == PaymentProvider.PAYPAL:
            event_type = str(payload["event_type"])
            if event_type != "PAYMENT.CAPTURE.COMPLETED":
                return None
            resource = payload["resource"]
            return _result(str(payload["id"]), event_type, resource["custom_id"], resource["id"], _major_to_minor(resource["amount"]["value"]))
        if provider == PaymentProvider.BTCPAY:
            event_type = str(payload["type"])
            if event_type not in {"InvoiceSettled", "InvoicePaymentSettled"}:
                return None
            return _result(str(payload.get("deliveryId") or payload["invoiceId"]), event_type, payload["metadata"]["booking_id"], payload["invoiceId"], _major_to_minor(payload["amount"]))
    except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
        raise AppError(400, "invalid_webhook_payload", "The successful-payment webhook is missing required fields.") from exc
    return None


def _result(event_id: str, event_type: str, booking_id: str, payment_id: str, amount_minor: int) -> SuccessfulPayment:
    return SuccessfulPayment(event_id, event_type, uuid.UUID(str(booking_id)), str(payment_id), amount_minor)


def _major_to_minor(amount: object) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
