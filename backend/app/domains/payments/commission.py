from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class PaymentSplit:
    platform_commission_minor: int
    host_share_minor: int


def split_payment(amount_minor: int, commission_bps: int) -> PaymentSplit:
    """Split a payment into the platform commission (rounded half-up) and the host share."""
    if amount_minor < 0:
        raise ValueError("Amount cannot be negative.")
    if not 0 <= commission_bps <= 10_000:
        raise ValueError("Commission must be between 0 and 10000 basis points.")
    commission = int(
        (Decimal(amount_minor) * Decimal(commission_bps) / Decimal(10_000)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )
    return PaymentSplit(platform_commission_minor=commission, host_share_minor=amount_minor - commission)
