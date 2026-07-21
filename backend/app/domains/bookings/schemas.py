import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domains.bookings.models import BookingStatus


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
