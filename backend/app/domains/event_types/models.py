import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LocationType(str, enum.Enum):
    """Where an event type's meetings happen; the conferencing domain turns online types into links."""

    NONE = "none"
    IN_PERSON = "in_person"
    PHONE = "phone"
    CUSTOM_LINK = "custom_link"
    GOOGLE_MEET = "google_meet"
    ZOOM = "zoom"
    MICROSOFT_TEAMS = "microsoft_teams"


class EventType(Base):
    __tablename__ = "event_types"
    __table_args__ = (
        UniqueConstraint("user_id", "slug"),
        Index(
            "uq_event_types_default_per_user",
            "user_id",
            unique=True,
            sqlite_where=text("is_default = 1"),
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    slot_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    price_minor: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Booking rules, enforced by AvailabilityService.slots() and therefore at booking time.
    buffer_before_minutes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    buffer_after_minutes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    minimum_notice_minutes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Booking window in host-local calendar days from today; None means unlimited.
    # No column default so an explicit None (unlimited) is stored as-is; the API defaults it to 60.
    max_days_in_advance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Max active bookings of this event type per host-local day; None means unlimited.
    daily_booking_limit: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    # Meeting location (LocationType value) and its detail: address, phone number or URL.
    location_type: Mapped[str] = mapped_column(String(32), default=LocationType.NONE.value, server_default=LocationType.NONE.value)
    location_value: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
