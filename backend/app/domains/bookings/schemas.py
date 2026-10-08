import uuid
from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.domains.bookings.models import BookingStatus, CancelledBy
from app.domains.event_types.models import LocationType
from app.domains.users.schemas import PublicUserRead


class BookingCreate(BaseModel):
    starts_at: datetime
    invitee_name: str = Field(min_length=2, max_length=120)
    invitee_email: EmailStr
    invitee_timezone: str = "UTC"
    notes: str | None = Field(default=None, max_length=2000)


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_type_id: uuid.UUID
    invitee_name: str
    invitee_email: EmailStr
    starts_at: datetime
    ends_at: datetime
    status: BookingStatus
    provider_payment_id: str | None
    booking_amount: int
    payment_expires_at: datetime


class PublicEventTypeRead(BaseModel):
    """Event type as shown to invitees before booking (read-only, no input validation)."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    title: str
    description: str | None
    duration_minutes: int
    slot_interval_minutes: int
    price_minor: int
    currency: str
    is_active: bool
    is_default: bool
    buffer_before_minutes: int
    buffer_after_minutes: int
    minimum_notice_minutes: int
    max_days_in_advance: int | None
    daily_booking_limit: int | None
    location_type: LocationType
    location_value: str | None

    @model_validator(mode="after")
    def hide_private_meeting_link(self) -> "PublicEventTypeRead":
        # A custom meeting link is only shared with confirmed invitees via email.
        if self.location_type == LocationType.CUSTOM_LINK:
            self.location_value = None
        return self


class PublicProfileRead(BaseModel):
    host: PublicUserRead
    event_types: list[PublicEventTypeRead]
    default_event_type_slug: str | None


def _ensure_utc(value: datetime) -> datetime:
    # SQLite returns naive values that were stored as UTC; always serialize with an offset.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


UTCDateTime = Annotated[datetime, AfterValidator(_ensure_utc)]


class HostBookingRead(BaseModel):
    """A booking as the host sees it in the dashboard."""

    id: uuid.UUID
    event_type_id: uuid.UUID
    event_type_title: str
    event_type_slug: str
    duration_minutes: int
    # Booking window of the event type (bounds the reschedule date picker); None means unlimited.
    max_days_in_advance: int | None
    invitee_name: str
    invitee_email: EmailStr
    invitee_timezone: str
    notes: str | None
    starts_at: UTCDateTime
    ends_at: UTCDateTime
    status: BookingStatus
    booking_amount: int
    currency: str
    provider_payment_id: str | None
    refund_status: str | None
    refunded_at: UTCDateTime | None
    meeting_url: str | None
    cancelled_at: UTCDateTime | None
    cancelled_by: CancelledBy | None
    cancellation_reason: str | None
    created_at: UTCDateTime


class HostBookingPage(BaseModel):
    items: list[HostBookingRead]
    total: int
    limit: int
    offset: int


class BookingCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class BookingRescheduleRequest(BaseModel):
    starts_at: datetime


class InviteeCancelRequest(BookingCancelRequest):
    token: str = Field(min_length=1, max_length=256)


class InviteeRescheduleRequest(BookingRescheduleRequest):
    token: str = Field(min_length=1, max_length=256)


class InviteeBookingRead(BaseModel):
    """A booking as the invitee sees it on the manage-booking page."""

    id: uuid.UUID
    status: BookingStatus
    event_type_title: str
    duration_minutes: int
    max_days_in_advance: int | None
    host_name: str
    host_timezone: str
    invitee_name: str
    invitee_email: EmailStr
    invitee_timezone: str
    notes: str | None
    starts_at: UTCDateTime
    ends_at: UTCDateTime
    meeting_url: str | None
    booking_amount: int
    currency: str
    refund_status: str | None
    cancelled_by: CancelledBy | None
    cancellation_reason: str | None
    # Self-service policy: changes are allowed until ``change_deadline``.
    can_cancel: bool
    can_reschedule: bool
    change_deadline: UTCDateTime
    cutoff_hours: int
