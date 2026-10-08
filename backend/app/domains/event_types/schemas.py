import re
import uuid

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, ValidationError, model_validator

from app.domains.event_types.models import LocationType


# Location types whose details come from an integration rather than the host.
_GENERATED_LOCATIONS = {LocationType.NONE, LocationType.GOOGLE_MEET, LocationType.ZOOM, LocationType.MICROSOFT_TEAMS}
_PHONE_PATTERN = re.compile(r"^\+?[0-9 ()\-.]{6,32}$")
_HTTP_URL = TypeAdapter(HttpUrl)


class EventTypeBase(BaseModel):
    # Store enum fields (location_type) as plain strings.
    model_config = ConfigDict(use_enum_values=True)

    title: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    duration_minutes: int = Field(default=30, ge=5, le=480)
    slot_interval_minutes: int = Field(default=30, ge=5, le=480)
    price_minor: int = Field(default=0, ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    is_active: bool = True
    is_default: bool = False
    buffer_before_minutes: int = Field(default=0, ge=0, le=240)
    buffer_after_minutes: int = Field(default=0, ge=0, le=240)
    # Up to 30 days of minimum notice.
    minimum_notice_minutes: int = Field(default=0, ge=0, le=43200)
    max_days_in_advance: int | None = Field(default=60, ge=1, le=730)
    daily_booking_limit: int | None = Field(default=None, ge=1, le=100)
    location_type: LocationType = LocationType.NONE
    # Address (in_person), phone number (phone) or meeting URL (custom_link).
    location_value: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def validate_location(self) -> "EventTypeBase":
        value = (self.location_value or "").strip()
        if LocationType(self.location_type) in _GENERATED_LOCATIONS:
            self.location_value = None
            return self
        if not value:
            raise ValueError("Enter the location details for this event type.")
        if self.location_type == LocationType.IN_PERSON and len(value) > 500:
            raise ValueError("Keep the address under 500 characters.")
        if self.location_type == LocationType.PHONE and not _PHONE_PATTERN.match(value):
            raise ValueError("Enter a valid phone number.")
        if self.location_type == LocationType.CUSTOM_LINK:
            try:
                _HTTP_URL.validate_python(value)
            except ValidationError as exc:
                raise ValueError("Enter a valid meeting link starting with https://.") from exc
            if not value.lower().startswith(("https://", "http://")):
                raise ValueError("Enter a valid meeting link starting with https://.")
        self.location_value = value
        return self


class EventTypeInput(EventTypeBase):
    pass


class EventTypeRead(EventTypeBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
