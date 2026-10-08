import logging
import uuid
from typing import Any

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.bookings.models import Booking
from app.domains.bookings.repository import BookingRepository
from app.domains.payments.gateways import GatewayEvent
from app.domains.payments.service import (
    PaymentAccountService,
    PaymentConfirmationService,
    PaymentOutcome,
    RefundService,
    require_gateway,
)
from app.domains.webhooks.models import WebhookEvent


logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.bookings = BookingRepository(db)

    def process(
        self,
        body: bytes,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, str]:
        gateway = require_gateway()
        if not gateway.verify_webhook(body, headers):
            raise AppError(status.HTTP_401_UNAUTHORIZED, "invalid_signature", "Invalid webhook signature.")
        try:
            event = gateway.parse_webhook(payload, headers)
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError(400, "invalid_webhook_payload", "The webhook is missing required fields.") from exc
        if not event:
            return {"status": "ignored"}

        # Idempotency: each provider event is processed once.
        if not self._record(gateway.provider.value, event, body, "processed"):
            return {"status": "duplicate"}

        if event.is_payment_success:
            return self._handle_payment(gateway.provider.value, event, body)
        if event.is_payout_status:
            found = PaymentAccountService(self.db).apply_provider_status(
                str(event.linked_account_id),
                str(event.activation_status),
                event.requirements,
            )
            self.db.commit()
            return {"status": "processed" if found else "ignored"}
        if event.is_refund_update:
            booking = self.bookings.get_by_refund_id(str(event.refund_id))
            if booking:
                RefundService.apply_refund_status(booking, str(event.refund_status))
            self.db.commit()
            return {"status": "processed" if booking else "ignored"}
        self.db.commit()
        return {"status": "ignored"}

    def _record(self, provider: str, event: GatewayEvent, body: bytes, event_status: str) -> bool:
        self.db.add(
            WebhookEvent(
                provider=provider,
                external_id=event.event_id,
                event_type=event.event_type,
                payload=body.decode(),
                status=event_status,
            )
        )
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            return False
        return True

    def _handle_payment(self, provider: str, event: GatewayEvent, body: bytes) -> dict[str, str]:
        booking = self._find_booking(event)
        if not booking:
            # Payments that don't belong to a booking (e.g. other platform products) are ignored.
            self.db.commit()
            return {"status": "ignored"}

        outcome = PaymentConfirmationService(self.db).confirm(
            booking,
            str(event.payment_id),
            int(event.amount_minor or 0),
        )
        if outcome == PaymentOutcome.CONFIRMED:
            return {"status": "processed"}
        if outcome == PaymentOutcome.DUPLICATE:
            return {"status": "duplicate"}

        # The slot was taken by someone else (or the booking closed) after the invitee paid.
        if outcome == PaymentOutcome.SLOT_TAKEN:
            # The confirmation rolled back, so record the event again.
            self._record(provider, event, body, "refunded")
        booking.provider_payment_id = str(event.payment_id)
        logger.warning(
            "Refunding late payment for booking %s (%s).",
            booking.id,
            outcome.value,
        )
        # Commits the refund together with the webhook event; on failure nothing is
        # recorded and the provider retries the webhook.
        RefundService(self.db).refund_booking(booking, f"booking_unavailable_after_payment:{outcome.value}")
        return {"status": "refunded"}

    def _find_booking(self, event: GatewayEvent) -> Booking | None:
        if event.order_id:
            booking = self.bookings.get_by_provider_order_id(event.order_id)
            if booking:
                return booking
        if event.booking_id:
            try:
                return self.db.get(Booking, uuid.UUID(event.booking_id))
            except ValueError:
                return None
        return None
