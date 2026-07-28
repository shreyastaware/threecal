from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.availability.service import AvailabilityService
from app.domains.billing.repository import BillingRepository
from app.domains.bookings.models import Booking, BookingStatus
from app.domains.bookings.schemas import BookingCreate
from app.domains.event_types.models import EventType
from app.domains.event_types.repository import EventTypeRepository
from app.domains.payments.repository import PaymentConfigRepository
from app.domains.users.models import User
from app.domains.users.repositories import UserRepository


class PublicBookingService:
    def __init__(self, db: Session) -> None:
        self.users = UserRepository(db)
        self.event_types = EventTypeRepository(db)

    def get_profile(
        self,
        username: str,
    ) -> tuple[User, list[EventType], EventType | None]:
        user = self.users.get_by_username(username)
        if not user or not user.is_active:
            raise AppError(
                status.HTTP_404_NOT_FOUND,
                "booking_profile_not_found",
                "Booking profile not found.",
            )
        events = self.event_types.list_active_for_user(user.id)
        default_event = self.event_types.get_default_for_user(
            user.id,
            active_only=True,
        )
        return user, events, default_event

    def resolve_page(
        self,
        username: str,
        event_slug: str,
    ) -> tuple[User, EventType]:
        user = self.users.get_by_username(username)
        event = (
            self.event_types.get_active_by_slug(user.id, event_slug)
            if user and user.is_active
            else None
        )
        if not user or not user.is_active or not event:
            raise AppError(
                status.HTTP_404_NOT_FOUND,
                "booking_page_not_found",
                "Booking page not found.",
            )
        return user, event


class BookingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, host: User, event_type: EventType, payload: BookingCreate) -> Booking:
        if event_type.price_minor:
            billing = BillingRepository(self.db).get_for_doctor(host.id)
            provider = PaymentConfigRepository(self.db).get_for_doctor(host.id)
            if not billing or not billing.ready or not provider:
                raise AppError(409, "doctor_payments_not_ready", "This doctor is not ready to accept paid bookings.")
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
            booking_amount=event_type.price_minor,
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
