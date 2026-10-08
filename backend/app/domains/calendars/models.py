import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CalendarProviderName(str, enum.Enum):
    GOOGLE = "google"
    MICROSOFT = "microsoft"


class ConnectionStatus(str, enum.Enum):
    ACTIVE = "active"
    # The refresh token was revoked/expired (invalid_grant); the host must reconnect.
    RECONNECT_REQUIRED = "reconnect_required"


class CalendarConnection(Base):
    """A host's OAuth connection to one calendar account."""

    __tablename__ = "calendar_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "account_email", name="uq_calendar_connections_user_provider_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    account_email: Mapped[str] = mapped_column(String(320))
    # OAuth tokens are encrypted at rest (app.core.encryption).
    encrypted_access_token: Mapped[str] = mapped_column(Text)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=ConnectionStatus.ACTIVE.value, server_default=ConnectionStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SelectedCalendar(Base):
    """A calendar of a connection that is checked for conflicts and/or receives new bookings."""

    __tablename__ = "selected_calendars"
    __table_args__ = (
        UniqueConstraint("connection_id", "external_calendar_id", name="uq_selected_calendars_connection_calendar"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calendar_connections.id", ondelete="CASCADE"), index=True)
    # Denormalized so per-host lookups (busy times, destination) need no join.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    external_calendar_id: Mapped[str] = mapped_column(String(1024))
    name: Mapped[str] = mapped_column(String(255))
    check_conflicts: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # At most one destination calendar per host (enforced by the service).
    is_destination: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class BookingCalendarEvent(Base):
    """An event Threecal created in a host calendar for a booking (one per booking and calendar)."""

    __tablename__ = "booking_calendar_events"
    __table_args__ = (
        UniqueConstraint("booking_id", "connection_id", "external_calendar_id", name="uq_booking_calendar_events_booking_calendar"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calendar_connections.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    external_calendar_id: Mapped[str] = mapped_column(String(1024))
    external_event_id: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
