import uuid
from datetime import datetime
from typing import Annotated

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


# Shared password policy for registration, password reset, and password change.
NewPassword = Annotated[str, Field(min_length=8, max_length=128)]

# Public booking pages live at /{username}, so a username must never shadow an app route.
# Keep in sync with frontend/features/scheduling/schemas.ts.
RESERVED_USERNAMES = frozenset(
    {
        "about", "account", "admin", "api", "app", "auth", "billing", "blog", "bookings", "contact",
        "dashboard", "docs", "forgot-password", "help", "integrations", "login", "logout", "onboarding",
        "payments", "pricing", "privacy", "public", "register", "reset-password", "settings", "signin",
        "signup", "static", "support", "terms", "verify-email", "www",
    }
)


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
        if value and value.lower() in RESERVED_USERNAMES:
            raise ValueError("That booking URL is reserved. Choose another one.")
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


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: NewPassword

    @model_validator(mode="after")
    def require_new_password(self) -> "PasswordChangeRequest":
        if self.current_password == self.new_password:
            raise ValueError("Choose a new password that differs from your current one.")
        return self


class AccountDeleteRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
