import uuid
from datetime import datetime, timedelta, timezone

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import generate_single_use_token, hash_single_use_token
from app.domains.auth.models import AuthTokenPurpose
from app.domains.auth.repository import AuthTokenRepository


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    # SQLite returns timezone-naive values that were stored as UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def token_ttl(purpose: AuthTokenPurpose) -> timedelta:
    if purpose is AuthTokenPurpose.PASSWORD_RESET:
        return timedelta(minutes=settings.password_reset_token_ttl_minutes)
    return timedelta(hours=settings.email_verification_token_ttl_hours)


class AuthTokenService:
    """Issues and redeems single-use emailed tokens. Callers own the transaction."""

    def __init__(self, db: Session) -> None:
        self.tokens = AuthTokenRepository(db)

    def issue(self, user_id: uuid.UUID, purpose: AuthTokenPurpose) -> str:
        now = utc_now()
        # Only the newest link of each kind works; older unused ones are retired.
        self.tokens.invalidate_unused(user_id, purpose, now)
        raw_token = generate_single_use_token()
        self.tokens.create(
            user_id=user_id,
            purpose=purpose,
            token_hash=hash_single_use_token(raw_token),
            expires_at=now + token_ttl(purpose),
        )
        return raw_token

    def consume(self, raw_token: str, purpose: AuthTokenPurpose) -> uuid.UUID:
        token = self.tokens.get_by_hash(hash_single_use_token(raw_token), purpose)
        now = utc_now()
        if not token or token.used_at is not None or as_utc(token.expires_at) <= now:
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_token",
                "This link is invalid or has expired. Please request a new one.",
            )
        token.used_at = now
        self.tokens.invalidate_unused(token.user_id, purpose, now)
        return token.user_id
