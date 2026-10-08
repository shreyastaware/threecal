"""Invitee manage-booking tokens.

The token handed to the invitee is an HMAC of the booking's random UUID under a
server-side key, so it is unguessable, and only ``sha256(token)`` is stored on the
booking. Because the token is derived rather than stored, every email (confirmation,
reschedule, reminder) can carry the same link even when it is sent later from
another process (for example after a payment webhook), while a database leak alone
does not reveal it. Clearing ``manage_token_hash`` revokes self-service for a booking.
"""

import base64
import hashlib
import hmac
import uuid

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings
from app.domains.bookings.models import Booking


def _key() -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"threecal-booking-manage-v1",
        info=b"invitee-manage-token",
    ).derive(settings.jwt_secret_key.encode())


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def derive_token(booking_id: uuid.UUID) -> str:
    digest = hmac.new(_key(), f"booking-manage:{booking_id}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def issue_token(booking: Booking) -> str:
    """Enable self-service for ``booking`` and return its token. Does not commit."""
    if booking.id is None:
        booking.id = uuid.uuid4()
    token = derive_token(booking.id)
    booking.manage_token_hash = hash_token(token)
    return token


def token_for(booking: Booking) -> str | None:
    """The invitee's token, or None when self-service is disabled for this booking."""
    return derive_token(booking.id) if booking.manage_token_hash else None


def verify_token(booking: Booking, token: str | None) -> bool:
    if not token or not booking.manage_token_hash:
        return False
    # Constant-time comparison of the presented token's hash against the stored one.
    return hmac.compare_digest(hash_token(token), booking.manage_token_hash)


def manage_url(booking: Booking) -> str | None:
    token = token_for(booking)
    if token is None:
        return None
    return f"{settings.frontend_url.rstrip('/')}/bookings/manage/{booking.id}?token={token}"
