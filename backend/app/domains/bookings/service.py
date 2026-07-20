from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.availability.service import AvailabilityService
from app.domains.bookings.models import Booking, BookingStatus
from app.domains.bookings.schemas import BookingCreate
from app.domains.event_types.models import EventType
from app.domains.users.models import User


class BookingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, host: User, event_type: EventType, payload: BookingCreate) -> Booking:
        try:
            ZoneInfo(payload.invitee_timezone)
        except ZoneInfoNotFoundError as exc:
            raise AppError(422, "invalid_timezone", "Unknown invitee timezone.") from exc
        requested = payload.starts_at.astimezone(ZoneInfo(host.timezone))
        slots = AvailabilityService(self.db).slots(host, event_type, requested.date(), requested.date(), host.timezone)
        if not any(slot["starts_at"] == requested for slot in slots):
            raise AppError(409, "slot_unavailable", "That time is no longer available.")
        booking = Booking(
            host_id=host.id,
            event_type_id=event_type.id,
            ends_at=payload.starts_at + timedelta(minutes=event_type.duration_minutes),
            payment_expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            status=BookingStatus.PENDING if event_type.price_minor else BookingStatus.CONFIRMED,
            **payload.model_dump(),
        )
        self.db.add(booking)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(409, "slot_unavailable", "That time is no longer available.") from exc
        self.db.refresh(booking)
        return booking
