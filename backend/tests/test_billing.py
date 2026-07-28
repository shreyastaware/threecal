import hashlib
import hmac
import json
import time
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.encryption import decrypt_secret, encrypt_secret
from app.domains.billing.models import PlatformBilling
from app.domains.billing.service import BillingCycleService, calculate_platform_fee
from app.domains.bookings.models import Booking, BookingStatus
from app.domains.event_types.models import EventType
from app.domains.payments.models import PaymentProvider
from app.domains.payments.repository import PaymentConfigRepository
from app.domains.users.models import User
from app.domains.webhooks.service import WebhookService


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_provider_secrets_are_encrypted_and_authenticated() -> None:
    encrypted = encrypt_secret("provider-secret")
    assert "provider-secret" not in encrypted
    assert decrypt_secret(encrypted) == "provider-secret"
    with pytest.raises(ValueError):
        decrypt_secret(encrypted[:-2] + "aa")


@pytest.mark.parametrize(
    ("earnings_minor", "fee_minor"),
    [
        (0, 0),
        (500_000, 0),
        (500_001, 20_000),
        (5_000_000, 20_000),
        (5_000_001, 100_000),
        (15_000_000, 100_000),
        (15_000_001, 300_000),
        (30_000_000, 300_000),
        (40_000_000, 1_200_000),
    ],
)
def test_volume_fee_tiers(earnings_minor: int, fee_minor: int) -> None:
    assert calculate_platform_fee(earnings_minor) == fee_minor


class FakeDodoClient:
    def __init__(self) -> None:
        self.status = "processing"
        self.charges: list[tuple[str, int, str]] = []

    def charge_subscription(self, subscription_id: str, amount_minor: int, invoice_id: str) -> str:
        self.charges.append((subscription_id, amount_minor, invoice_id))
        return "pay_monthly"

    def payment_status(self, payment_id: str) -> str:
        assert payment_id == "pay_monthly"
        return self.status


def test_billing_cycle_resets_only_after_successful_charge(db: Session) -> None:
    doctor = User(email="doctor@example.com", full_name="Doctor", password_hash="unused")
    db.add(doctor)
    db.flush()
    billing = PlatformBilling(
        doctor_id=doctor.id,
        payment_method_id="pm_123",
        dodopayments_customer_id="cus_123",
        dodopayments_subscription_id="sub_123",
        current_cycle_start=datetime(2026, 6, 1),
        current_cycle_earnings=6_000_000,
    )
    db.add(billing)
    db.commit()
    client = FakeDodoClient()
    service = BillingCycleService(db, client)  # type: ignore[arg-type]

    first = service.run(datetime(2026, 7, 2))
    assert first.pending == 1
    assert billing.current_cycle_earnings == 6_000_000
    assert client.charges[0][1] == 100_000

    client.status = "succeeded"
    second = service.run(datetime(2026, 7, 2))
    assert second.processed == 1
    assert billing.current_cycle_earnings == 0
    assert billing.current_cycle_start == datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert len(client.charges) == 1


def test_verified_webhook_confirms_once_and_accumulates_earnings(db: Session) -> None:
    doctor = User(email="webhook@example.com", full_name="Webhook Doctor", password_hash="unused")
    db.add(doctor)
    db.flush()
    event_type = EventType(user_id=doctor.id, title="Visit", slug="visit", price_minor=75_000)
    db.add(event_type)
    db.flush()
    booking = Booking(
        host_id=doctor.id,
        event_type_id=event_type.id,
        invitee_name="Patient",
        invitee_email="patient@example.com",
        invitee_timezone="UTC",
        starts_at=datetime.now(timezone.utc) + timedelta(days=1),
        ends_at=datetime.now(timezone.utc) + timedelta(days=1, minutes=30),
        status=BookingStatus.PENDING,
        booking_amount=75_000,
        payment_expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    billing = PlatformBilling(doctor_id=doctor.id, payment_method_id="pm", dodopayments_customer_id="cus", dodopayments_subscription_id="sub")
    db.add_all([booking, billing])
    secret = "whsec_doctor"
    PaymentConfigRepository(db).create(doctor.id, PaymentProvider.STRIPE, {"access_token": "sk_test"}, "acct_123", secret)
    db.commit()

    payload = {
        "id": "evt_123",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_123", "amount_received": 75_000, "metadata": {"booking_id": str(booking.id), "doctor_id": str(doctor.id)}}},
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = int(time.time())
    signature = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    headers = {"stripe-signature": f"t={timestamp},v1={signature}"}

    assert WebhookService(db).process(PaymentProvider.STRIPE, doctor.id, body, headers, payload) == {"status": "processed"}
    assert WebhookService(db).process(PaymentProvider.STRIPE, doctor.id, body, headers, payload) == {"status": "duplicate"}
    db.refresh(booking)
    db.refresh(billing)
    assert booking.status == BookingStatus.CONFIRMED
    assert booking.provider_payment_id == "pi_123"
    assert billing.current_cycle_earnings == 75_000
