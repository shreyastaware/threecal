"""Domain event subscriptions for calendar sync (registered once at app startup)."""

import uuid

from app.core import database
from app.core.events import BOOKING_CANCELLED, BOOKING_CONFIRMED, BOOKING_RESCHEDULED, DomainEvent, event_bus
from app.domains.calendars.sync import CalendarSyncService


# Runs after conferencing (10) so meeting links are known, before emails (100).
CALENDAR_SYNC_PRIORITY = 20


def _booking_id(event: DomainEvent) -> uuid.UUID:
    return uuid.UUID(str(event.payload["booking_id"]))


def on_booking_confirmed(event: DomainEvent) -> None:
    with database.SessionLocal() as db:
        CalendarSyncService(db).on_confirmed(_booking_id(event))


def on_booking_rescheduled(event: DomainEvent) -> None:
    with database.SessionLocal() as db:
        CalendarSyncService(db).on_rescheduled(_booking_id(event))


def on_booking_cancelled(event: DomainEvent) -> None:
    with database.SessionLocal() as db:
        CalendarSyncService(db).on_cancelled(_booking_id(event))


def register_calendar_handlers() -> None:
    event_bus.subscribe(BOOKING_CONFIRMED, on_booking_confirmed, priority=CALENDAR_SYNC_PRIORITY)
    event_bus.subscribe(BOOKING_RESCHEDULED, on_booking_rescheduled, priority=CALENDAR_SYNC_PRIORITY)
    event_bus.subscribe(BOOKING_CANCELLED, on_booking_cancelled, priority=CALENDAR_SYNC_PRIORITY)
