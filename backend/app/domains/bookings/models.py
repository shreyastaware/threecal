import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CancelledBy(str, enum.Enum):
    HOST = "host"
    INVITEE = "invitee"


class Booking(Base):
    __tablename__ = "bookings"
    # Only pending and confirmed bookings hold a slot, so cancelled or expired
    # bookings never block a new booking at the same start time.
    __table_args__ = (
        Index(
            "uq_booking_host_start_active",
            "host_id",
            "starts_at",
            unique=True,
            sqlite_where=text("status IN ('PENDING', 'CONFIRMED')"),
            postgresql_where=text("status IN ('PENDING', 'CONFIRMED')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    host_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event_types.id", ondelete="RESTRICT"), index=True)
    invitee_name: Mapped[str] = mapped_column(String(120))
    invitee_email: Mapped[str] = mapped_column(String(320), index=True)
    invitee_timezone: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), default=BookingStatus.PENDING)
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    # Stored in the event currency's minor unit (paise for INR).
    booking_amount: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    payment_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Provider order created at checkout; provider_payment_id holds the captured payment.
    provider_order_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    # Platform share of booking_amount fixed at checkout, in minor units.
    platform_commission_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    refund_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    refund_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Join link for online meetings, filled by the conferencing integration once confirmed.
    meeting_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # SHA-256 of the invitee's manage-booking token; the raw token only travels in emails.
    manage_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # iCalendar SEQUENCE: bumped on every reschedule/cancellation so calendar clients update the event.
    sequence: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # "host" or "invitee" (see CancelledBy).
    cancelled_by: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
