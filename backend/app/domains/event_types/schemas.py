import uuid

from pydantic import BaseModel, ConfigDict, Field


class EventTypeInput(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(default=None, max_length=2000)
    duration_minutes: int = Field(default=30, ge=5, le=480)
    slot_interval_minutes: int = Field(default=30, ge=5, le=480)
    price_minor: int = Field(default=0, ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    is_active: bool = True


class EventTypeRead(EventTypeInput):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
