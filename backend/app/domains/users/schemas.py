import uuid
from datetime import datetime

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    username: str | None
    bio: str | None
    timezone: str
    avatar_url: str | None
    is_active: bool
    is_email_verified: bool
    created_at: datetime


class UserProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    username: str | None = Field(default=None, min_length=3, max_length=50, pattern=r"^[a-z0-9_-]+$")
    bio: str | None = Field(default=None, max_length=1000)
    timezone: str | None = None
    avatar_url: str | None = Field(default=None, max_length=2048)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        return value.lower() if value else value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value:
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("Unknown timezone") from exc
        return value


class PublicUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str
    username: str
    bio: str | None
    timezone: str
    avatar_url: str | None
