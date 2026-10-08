import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.events import BOOKING_CANCELLED, BOOKING_CONFIRMED, BOOKING_RESCHEDULED, DomainEvent, event_bus
from app.domains.availability.service import AvailabilityService
from app.domains.bookings.manage_token import issue_token, verify_token
from app.domains.bookings.models import Booking, BookingStatus, CancelledBy
from app.domains.bookings.repository import BookingRepository, BookingScope, as_utc, utc_now
from app.domains.bookings.schemas import BookingCreate, HostBookingPage, HostBookingRead, InviteeBookingRead
from app.domains.event_types.models import EventType
from app.domains.event_types.repository import EventTypeRepository
from app.domains.payments.repository import PaymentAccountRepository
from app.domains.payments.service import RefundService
from app.domains.users.models import User
from app.domains.users.repositories import UserRepository


DEFAULT_PAGE_SIZE = 20
MAX_SLOT_RANGE_DAYS = 31


def publish_booking_confirmed(booking: Booking) -> None:
    """Announce a newly confirmed booking. Call once per booking, after the commit."""
    event_bus.publish(DomainEvent(BOOKING_CONFIRMED, {"booking_id": str(booking.id)}))


def booking_not_found() -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, "booking_not_found", "Booking not found.")


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
            # Paid bookings are routed to the host's linked payout account, so it must be active.
            payout_account = PaymentAccountRepository(self.db).get_for_user(host.id)
            if not payout_account or not payout_account.payouts_enabled:
                raise AppError(409, "host_payments_not_ready", "This host is not ready to accept paid bookings.")
        try:
            ZoneInfo(payload.invitee_timezone)
        except ZoneInfoNotFoundError as exc:
            raise AppError(422, "invalid_timezone", "Unknown invitee timezone.") from exc
        requested = payload.starts_at.astimezone(ZoneInfo(host.timezone))
        slots = AvailabilityService(self.db).slots(host, event_type, requested.date(), requested.date(), host.timezone)
        if not any(slot["starts_at"] == requested for slot in slots):
            raise AppError(409, "slot_unavailable", "That time is no longer available.")
        # Store UTC so SQLite, which drops offsets, keeps comparable values.
        starts_at = payload.starts_at.astimezone(timezone.utc)
        booking = Booking(
            host_id=host.id,
            event_type_id=event_type.id,
            ends_at=starts_at + timedelta(minutes=event_type.duration_minutes),
            payment_expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            status=BookingStatus.PENDING if event_type.price_minor else BookingStatus.CONFIRMED,
            booking_amount=event_type.price_minor,
            **payload.model_dump(exclude={"starts_at"}),
            starts_at=starts_at,
        )
        # Enables the invitee's emailed manage-booking link.
        issue_token(booking)
        # Release the slot if an earlier unpaid booking at this time has expired.
        BookingRepository(self.db).expire_stale_pending(host.id, starts_at)
        self.db.add(booking)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(409, "slot_unavailable", "That time is no longer available.") from exc
        self.db.refresh(booking)
        # Free bookings are confirmed immediately; paid ones once the payment is captured.
        if booking.status == BookingStatus.CONFIRMED:
            publish_booking_confirmed(booking)
        return booking


class BookingExpiryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def expire_stale(self) -> int:
        expired = BookingRepository(self.db).expire_stale_pending()
        self.db.commit()
        return expired


class BookingLifecycleService:
    """Cancels and reschedules bookings on behalf of hosts and invitees."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = BookingRepository(db)

    def load_context(self, booking: Booking) -> tuple[EventType, User]:
        event_type = self.db.get(EventType, booking.event_type_id)
        host = self.db.get(User, booking.host_id)
        if event_type is None or host is None:
            raise booking_not_found()
        return event_type, host

    def cancel(self, booking: Booking, *, cancelled_by: CancelledBy, reason: str | None = None) -> Booking:
        """Cancel a pending or confirmed booking, fully refunding a captured payment first."""
        if booking.status not in {BookingStatus.PENDING, BookingStatus.CONFIRMED}:
            raise AppError(status.HTTP_409_CONFLICT, "booking_not_cancellable", "Only upcoming bookings can be cancelled.")
        if as_utc(booking.starts_at) <= utc_now():
            raise AppError(status.HTTP_409_CONFLICT, "booking_already_started", "This booking has already started.")
        reason = (reason or "").strip() or None
        was_confirmed = booking.status == BookingStatus.CONFIRMED
        if was_confirmed and booking.provider_payment_id and booking.booking_amount > 0:
            # Idempotent and committed on its own; a provider failure aborts the cancellation.
            RefundService(self.db).refund_booking(booking, f"cancelled_by_{cancelled_by.value}")
        # A pending booking paid after this point is refunded automatically by the payment webhook.
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = utc_now()
        booking.cancelled_by = cancelled_by.value
        booking.cancellation_reason = reason
        booking.sequence = (booking.sequence or 0) + 1
        self.db.commit()
        if was_confirmed:
            event_bus.publish(
                DomainEvent(
                    BOOKING_CANCELLED,
                    {"booking_id": str(booking.id), "cancelled_by": cancelled_by.value, "reason": reason},
                )
            )
        return booking

    def reschedule(self, booking: Booking, starts_at: datetime, *, rescheduled_by: CancelledBy) -> Booking:
        """Move a confirmed booking to another valid slot, keeping its payment."""
        if booking.status != BookingStatus.CONFIRMED:
            raise AppError(status.HTTP_409_CONFLICT, "booking_not_reschedulable", "Only confirmed bookings can be rescheduled.")
        if as_utc(booking.starts_at) <= utc_now():
            raise AppError(status.HTTP_409_CONFLICT, "booking_already_started", "This booking has already started.")
        event_type, host = self.load_context(booking)
        new_start = as_utc(starts_at).astimezone(timezone.utc)
        previous_start, previous_end = as_utc(booking.starts_at), as_utc(booking.ends_at)
        if new_start == previous_start:
            raise AppError(status.HTTP_409_CONFLICT, "same_time", "Choose a different time to reschedule.")
        requested = new_start.astimezone(ZoneInfo(host.timezone))
        slots = AvailabilityService(self.db).slots(
            host,
            event_type,
            requested.date(),
            requested.date(),
            host.timezone,
            exclude_booking_id=booking.id,
        )
        if not any(slot["starts_at"] == requested for slot in slots):
            raise AppError(status.HTTP_409_CONFLICT, "slot_unavailable", "That time is no longer available.")
        booking.starts_at = new_start
        booking.ends_at = new_start + timedelta(minutes=event_type.duration_minutes)
        booking.sequence = (booking.sequence or 0) + 1
        self.repository.expire_stale_pending(host.id, new_start)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(status.HTTP_409_CONFLICT, "slot_unavailable", "That time is no longer available.") from exc
        event_bus.publish(
            DomainEvent(
                BOOKING_RESCHEDULED,
                {
                    "booking_id": str(booking.id),
                    "previous_starts_at": previous_start.isoformat(),
                    "previous_ends_at": previous_end.isoformat(),
                    "rescheduled_by": rescheduled_by.value,
                },
            )
        )
        return booking

    def reschedule_slots(self, booking: Booking, start: date, end: date, viewer_timezone: str) -> list[dict[str, datetime]]:
        """Slots the booking could move to (its own time does not block them)."""
        if end < start or (end - start).days > MAX_SLOT_RANGE_DAYS:
            raise AppError(422, "invalid_date_range", f"Choose a date range of up to {MAX_SLOT_RANGE_DAYS} days.")
        event_type, host = self.load_context(booking)
        try:
            slots = AvailabilityService(self.db).slots(host, event_type, start, end, viewer_timezone, exclude_booking_id=booking.id)
        except ZoneInfoNotFoundError as exc:
            raise AppError(422, "invalid_timezone", "Unknown timezone.") from exc
        current = as_utc(booking.starts_at)
        return [slot for slot in slots if slot["starts_at"] != current]


class HostBookingService:
    """Booking management for the authenticated host."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = BookingRepository(db)
        self.lifecycle = BookingLifecycleService(db)

    def list(
        self,
        host: User,
        scope: BookingScope,
        *,
        event_type_id: uuid.UUID | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> HostBookingPage:
        items, total = self.repository.list_for_host(host.id, scope, event_type_id=event_type_id, limit=limit, offset=offset)
        return HostBookingPage(items=[self.to_read(item) for item in items], total=total, limit=limit, offset=offset)

    def get(self, host: User, booking_id: uuid.UUID) -> Booking:
        booking = self.repository.get_for_host(host.id, booking_id)
        if booking is None:
            raise booking_not_found()
        return booking

    def cancel(self, host: User, booking_id: uuid.UUID, reason: str | None) -> HostBookingRead:
        booking = self.lifecycle.cancel(self.get(host, booking_id), cancelled_by=CancelledBy.HOST, reason=reason)
        return self.to_read(booking)

    def reschedule(self, host: User, booking_id: uuid.UUID, starts_at: datetime) -> HostBookingRead:
        booking = self.lifecycle.reschedule(self.get(host, booking_id), starts_at, rescheduled_by=CancelledBy.HOST)
        return self.to_read(booking)

    def to_read(self, booking: Booking) -> HostBookingRead:
        event_type = self.db.get(EventType, booking.event_type_id)
        if event_type is None:
            raise booking_not_found()
        return HostBookingRead.model_validate(
            {
                **_booking_fields(booking),
                "event_type_title": event_type.title,
                "event_type_slug": event_type.slug,
                "max_days_in_advance": event_type.max_days_in_advance,
                "duration_minutes": int((as_utc(booking.ends_at) - as_utc(booking.starts_at)).total_seconds() // 60),
                "invitee_email": booking.invitee_email,
                "provider_payment_id": booking.provider_payment_id,
                "refunded_at": booking.refunded_at,
                "cancelled_at": booking.cancelled_at,
                "created_at": booking.created_at,
                "currency": event_type.currency,
            }
        )


def _booking_fields(booking: Booking) -> dict[str, object]:
    return {
        "id": booking.id,
        "event_type_id": booking.event_type_id,
        "status": booking.status,
        "invitee_name": booking.invitee_name,
        "invitee_timezone": booking.invitee_timezone,
        "notes": booking.notes,
        "starts_at": booking.starts_at,
        "ends_at": booking.ends_at,
        "booking_amount": booking.booking_amount,
        "refund_status": booking.refund_status,
        "meeting_url": booking.meeting_url,
        "cancelled_by": booking.cancelled_by,
        "cancellation_reason": booking.cancellation_reason,
    }


class InviteeBookingService:
    """Token-authenticated self-service for invitees, limited by the change cutoff."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.lifecycle = BookingLifecycleService(db)

    @staticmethod
    def change_deadline(booking: Booking) -> datetime:
        return as_utc(booking.starts_at) - timedelta(hours=settings.invitee_change_cutoff_hours)

    def can_change(self, booking: Booking, now: datetime | None = None) -> bool:
        return booking.status == BookingStatus.CONFIRMED and (now or utc_now()) < self.change_deadline(booking)

    def get(self, booking_id: uuid.UUID, token: str | None) -> Booking:
        booking = self.db.get(Booking, booking_id)
        # Unknown bookings and wrong tokens look the same, so ids cannot be probed.
        if booking is None or not verify_token(booking, token):
            raise booking_not_found()
        return booking

    def cancel(self, booking_id: uuid.UUID, token: str, reason: str | None) -> InviteeBookingRead:
        booking = self.get(booking_id, token)
        self._require_change_window(booking)
        # Invitee cancellations inside the allowed window are fully refunded.
        return self.to_read(self.lifecycle.cancel(booking, cancelled_by=CancelledBy.INVITEE, reason=reason))

    def reschedule(self, booking_id: uuid.UUID, token: str, starts_at: datetime) -> InviteeBookingRead:
        booking = self.get(booking_id, token)
        self._require_change_window(booking)
        return self.to_read(self.lifecycle.reschedule(booking, starts_at, rescheduled_by=CancelledBy.INVITEE))

    def slots(self, booking_id: uuid.UUID, token: str, start: date, end: date, viewer_timezone: str) -> list[dict[str, datetime]]:
        booking = self.get(booking_id, token)
        self._require_change_window(booking)
        return self.lifecycle.reschedule_slots(booking, start, end, viewer_timezone)

    def _require_change_window(self, booking: Booking) -> None:
        if booking.status != BookingStatus.CONFIRMED:
            raise AppError(status.HTTP_409_CONFLICT, "booking_not_changeable", "This booking can no longer be changed.")
        if not self.can_change(booking):
            hours = settings.invitee_change_cutoff_hours
            raise AppError(
                status.HTTP_409_CONFLICT,
                "change_window_closed",
                f"Bookings can only be changed online until {hours} hours before the start. Please contact your host.",
            )

    def to_read(self, booking: Booking) -> InviteeBookingRead:
        event_type, host = self.lifecycle.load_context(booking)
        can_change = self.can_change(booking)
        return InviteeBookingRead.model_validate(
            {
                **_booking_fields(booking),
                "event_type_title": event_type.title,
                "duration_minutes": int((as_utc(booking.ends_at) - as_utc(booking.starts_at)).total_seconds() // 60),
                "host_name": host.full_name,
                "max_days_in_advance": event_type.max_days_in_advance,
                "host_timezone": host.timezone,
                "invitee_email": booking.invitee_email,
                "currency": event_type.currency,
                "can_cancel": can_change,
                "can_reschedule": can_change,
                "change_deadline": self.change_deadline(booking),
                "cutoff_hours": settings.invitee_change_cutoff_hours,
            }
        )
