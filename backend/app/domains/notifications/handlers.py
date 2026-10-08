"""Domain-event subscribers that email booking updates.

Handlers run on the event bus worker thread, so each opens its own session and
receives only ids in the payload. They subscribe at priority 100 so integrations
that run first (conferencing sets ``bookings.meeting_url`` at priority 10) are
reflected in the emails.
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core import database
from app.core.events import BOOKING_CANCELLED, BOOKING_CONFIRMED, BOOKING_RESCHEDULED, DomainEvent, event_bus
from app.domains.email import service as email_service
from app.domains.notifications.repository import BookingReminderRepository
from app.domains.notifications.service import BookingNotificationService

NOTIFICATION_PRIORITY = 100


def _notifications(db: Session) -> BookingNotificationService:
    # Resolved per call so the provider can be switched (or replaced in tests) at runtime.
    return BookingNotificationService(db, email_service.EmailService(email_service.get_email_provider()))


def handle_booking_confirmed(event: DomainEvent) -> None:
    with database.SessionLocal() as db:
        _notifications(db).booking_confirmed(uuid.UUID(event.payload["booking_id"]))


def handle_booking_cancelled(event: DomainEvent) -> None:
    with database.SessionLocal() as db:
        _notifications(db).booking_cancelled(uuid.UUID(event.payload["booking_id"]))


def handle_booking_rescheduled(event: DomainEvent) -> None:
    booking_id = uuid.UUID(event.payload["booking_id"])
    with database.SessionLocal() as db:
        # Reminders already sent for the old time must go out again for the new one.
        BookingReminderRepository(db).reset_for_booking(booking_id)
        _notifications(db).booking_rescheduled(
            booking_id,
            datetime.fromisoformat(event.payload["previous_starts_at"]),
            datetime.fromisoformat(event.payload["previous_ends_at"]),
            event.payload.get("rescheduled_by"),
        )


def register_notification_handlers() -> None:
    """Subscribe booking emails to domain events. Safe to call more than once."""
    event_bus.subscribe(BOOKING_CONFIRMED, handle_booking_confirmed, priority=NOTIFICATION_PRIORITY)
    event_bus.subscribe(BOOKING_CANCELLED, handle_booking_cancelled, priority=NOTIFICATION_PRIORITY)
    event_bus.subscribe(BOOKING_RESCHEDULED, handle_booking_rescheduled, priority=NOTIFICATION_PRIORITY)
