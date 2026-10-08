"""Domain event subscriptions for meeting links (registered once at app startup)."""

import uuid

from app.core import database
from app.core.events import BOOKING_CANCELLED, BOOKING_CONFIRMED, BOOKING_RESCHEDULED, DomainEvent, event_bus
from app.domains.conferencing.service import MeetingService


# Runs first: calendar sync (20) and emails (100) include the meeting link it stores.
CONFERENCING_PRIORITY = 10


def _booking_id(event: DomainEvent) -> uuid.UUID:
    return uuid.UUID(str(event.payload["booking_id"]))


def on_booking_confirmed(event: DomainEvent) -> None:
    with database.SessionLocal() as db:
        MeetingService(db).on_confirmed(_booking_id(event))


def on_booking_rescheduled(event: DomainEvent) -> None:
    with database.SessionLocal() as db:
        MeetingService(db).on_rescheduled(_booking_id(event))


def on_booking_cancelled(event: DomainEvent) -> None:
    with database.SessionLocal() as db:
        MeetingService(db).on_cancelled(_booking_id(event))


def register_conferencing_handlers() -> None:
    event_bus.subscribe(BOOKING_CONFIRMED, on_booking_confirmed, priority=CONFERENCING_PRIORITY)
    event_bus.subscribe(BOOKING_RESCHEDULED, on_booking_rescheduled, priority=CONFERENCING_PRIORITY)
    event_bus.subscribe(BOOKING_CANCELLED, on_booking_cancelled, priority=CONFERENCING_PRIORITY)
