import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.domains.bookings.models import Booking, BookingStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    # SQLite returns timezone-naive values that were stored as UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def is_payment_window_open(booking: Booking, now: datetime | None = None) -> bool:
    return as_utc(booking.payment_expires_at) > (now or utc_now())


class BookingScope(str, enum.Enum):
    UPCOMING = "upcoming"
    PAST = "past"
    CANCELLED = "cancelled"


def active_booking_clause(now: datetime) -> object:
    """Bookings that currently hold their slot: confirmed, or pending with an open payment window."""
    return or_(
        Booking.status == BookingStatus.CONFIRMED,
        and_(Booking.status == BookingStatus.PENDING, Booking.payment_expires_at > now),
    )


class BookingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active_overlapping(self, host_id: uuid.UUID, range_start: datetime, range_end: datetime) -> list[Booking]:
        return list(
            self.db.scalars(
                select(Booking).where(
                    Booking.host_id == host_id,
                    Booking.starts_at < range_end,
                    Booking.ends_at > range_start,
                    active_booking_clause(utc_now()),  # type: ignore[arg-type]
                )
            )
        )

    def get_by_provider_order_id(self, order_id: str) -> Booking | None:
        return self.db.scalar(select(Booking).where(Booking.provider_order_id == order_id))

    def get_by_refund_id(self, refund_id: str) -> Booking | None:
        return self.db.scalar(select(Booking).where(Booking.refund_id == refund_id))

    def expire_stale_pending(self, host_id: uuid.UUID | None = None, starts_at: datetime | None = None) -> int:
        """Mark unpaid bookings whose payment window has closed as expired, releasing their slots."""
        statement = update(Booking).where(
            Booking.status == BookingStatus.PENDING,
            Booking.payment_expires_at <= utc_now(),
        )
        if host_id is not None:
            statement = statement.where(Booking.host_id == host_id)
        if starts_at is not None:
            statement = statement.where(Booking.starts_at == starts_at)
        result = self.db.execute(statement.values(status=BookingStatus.EXPIRED).execution_options(synchronize_session=False))
        return int(result.rowcount or 0)  # type: ignore[attr-defined]

    def count_upcoming_confirmed_for_host(self, host_id: uuid.UUID) -> int:
        """Confirmed bookings that have not started yet (used to guard account deletion)."""
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.host_id == host_id,
                    Booking.status == BookingStatus.CONFIRMED,
                    Booking.starts_at > utc_now(),
                )
            )
            or 0
        )

    def get_for_host(self, host_id: uuid.UUID, booking_id: uuid.UUID) -> Booking | None:
        return self.db.scalar(select(Booking).where(Booking.id == booking_id, Booking.host_id == host_id))

    def list_for_host(
        self,
        host_id: uuid.UUID,
        scope: BookingScope,
        *,
        event_type_id: uuid.UUID | None = None,
        limit: int = 20,
        offset: int = 0,
        now: datetime | None = None,
    ) -> tuple[list[Booking], int]:
        """Page through a host's bookings for one dashboard tab, with the total count."""
        now = now or utc_now()
        if scope == BookingScope.UPCOMING:
            condition = and_(active_booking_clause(now), Booking.ends_at > now)  # type: ignore[arg-type]
            order = (Booking.starts_at.asc(),)
        elif scope == BookingScope.PAST:
            condition = and_(Booking.status == BookingStatus.CONFIRMED, Booking.ends_at <= now)
            order = (Booking.starts_at.desc(),)
        else:
            # Cancelled, expired, and unpaid holds whose payment window has closed.
            condition = or_(
                Booking.status.in_([BookingStatus.CANCELLED, BookingStatus.EXPIRED]),
                and_(Booking.status == BookingStatus.PENDING, Booking.payment_expires_at <= now),
            )
            order = (Booking.starts_at.desc(),)
        filters = [Booking.host_id == host_id, condition]
        if event_type_id is not None:
            filters.append(Booking.event_type_id == event_type_id)
        total = int(self.db.scalar(select(func.count()).select_from(Booking).where(*filters)) or 0)
        items = list(self.db.scalars(select(Booking).where(*filters).order_by(*order).limit(limit).offset(offset)))
        return items, total

    def list_confirmed_starting_between(self, range_start: datetime, range_end: datetime) -> list[Booking]:
        """Confirmed bookings with ``range_start < starts_at <= range_end`` (used by reminders)."""
        return list(
            self.db.scalars(
                select(Booking)
                .where(
                    Booking.status == BookingStatus.CONFIRMED,
                    Booking.starts_at > range_start,
                    Booking.starts_at <= range_end,
                )
                .order_by(Booking.starts_at.asc())
            )
        )
