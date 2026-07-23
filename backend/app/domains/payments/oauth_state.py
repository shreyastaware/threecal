import base64
import hashlib
import hmac
import struct
import time
import uuid

from app.core.config import settings
from app.domains.payments.models import PaymentProvider


_STATE_VERSION = 1
_STATE_TTL_SECONDS = 10 * 60
_PROVIDER_CODES = {
    PaymentProvider.STRIPE: 1,
    PaymentProvider.PAYPAL: 2,
    PaymentProvider.RAZORPAY: 3,
    PaymentProvider.CASHFREE: 4,
}
_CODE_PROVIDERS = {code: provider for provider, code in _PROVIDER_CODES.items()}


def create_oauth_state(doctor_id: uuid.UUID, provider: PaymentProvider) -> str:
    provider_code = _PROVIDER_CODES.get(provider)
    if provider_code is None:
        raise ValueError("Provider does not support OAuth.")

    payload = struct.pack(
        ">BBI16s",
        _STATE_VERSION,
        provider_code,
        int(time.time()),
        doctor_id.bytes,
    )
    signature = hmac.new(
        settings.jwt_secret_key.encode(),
        payload,
        hashlib.sha256,
    ).digest()[:16]
    return base64.urlsafe_b64encode(payload + signature).decode().rstrip("=")


def read_oauth_state(state: str) -> tuple[uuid.UUID, PaymentProvider]:
    try:
        encoded = state + "=" * (-len(state) % 4)
        decoded = base64.urlsafe_b64decode(encoded.encode())
        payload, signature = decoded[:-16], decoded[-16:]
        expected = hmac.new(
            settings.jwt_secret_key.encode(),
            payload,
            hashlib.sha256,
        ).digest()[:16]
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        version, provider_code, issued_at, doctor_bytes = struct.unpack(
            ">BBI16s",
            payload,
        )
        now = int(time.time())
        if (
            version != _STATE_VERSION
            or issued_at > now + 30
            or now - issued_at > _STATE_TTL_SECONDS
        ):
            raise ValueError
        return uuid.UUID(bytes=doctor_bytes), _CODE_PROVIDERS[provider_code]
    except (KeyError, TypeError, ValueError, struct.error) as exc:
        raise ValueError("The OAuth state is invalid or expired.") from exc
