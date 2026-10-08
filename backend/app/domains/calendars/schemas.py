import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AuthorizationUrlRead(BaseModel):
    authorization_url: str


class CalendarConnectionRead(BaseModel):
    id: uuid.UUID
    provider: str
    account_email: str
    status: str
    created_at: datetime
    # External ids of the calendars checked for conflicts.
    conflict_calendar_ids: list[str]
    # External id of the calendar new bookings are written to, if it belongs to this connection.
    destination_calendar_id: str | None


class ProviderCalendarRead(BaseModel):
    id: str
    name: str
    is_primary: bool
    can_write: bool
    check_conflicts: bool
    is_destination: bool


class CalendarConnectionUpdate(BaseModel):
    conflict_calendar_ids: list[str] = Field(default_factory=list, max_length=50)
    # None leaves this connection without the destination calendar.
    destination_calendar_id: str | None = Field(default=None, max_length=1024)
