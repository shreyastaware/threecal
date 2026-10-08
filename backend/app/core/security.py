import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt  # type: ignore[import-untyped]
from pwdlib import PasswordHash

from app.core.config import settings


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(subject: str, token_version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        # Bumped on password change/reset so previously issued tokens stop working.
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


@dataclass(frozen=True)
class AccessTokenClaims:
    subject: str
    token_version: int


def decode_access_token(token: str) -> str | None:
    claims = decode_access_token_claims(token)
    return claims.subject if claims else None


def decode_access_token_claims(token: str) -> AccessTokenClaims | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        return None

    subject = payload.get("sub")
    if payload.get("type") != "access" or not isinstance(subject, str):
        return None
    # Tokens issued before versioning existed carry no "ver" claim and map to version 0.
    version = payload.get("ver", 0)
    if not isinstance(version, int):
        return None
    return AccessTokenClaims(subject=subject, token_version=version)


def generate_single_use_token() -> str:
    return secrets.token_urlsafe(32)


def hash_single_use_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
