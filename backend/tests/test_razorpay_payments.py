import json
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.domains.email import service as email_service
from app.domains.bookings.models import Booking, BookingStatus
from app.domains.email.providers import ConsoleEmailProvider
from app.domains.payments.commission import split_payment
from app.domains.payments.service import RefundService
from app.main import app
from tests.razorpay_fakes import (
    ACCOUNT_ID,
    ACCOUNT_PAYLOAD,
    KEY_ID,
    FakeRazorpay,
    razorpay,  # noqa: F401
    sign_checkout,
    sign_webhook,
)


API = "/api/v1"
TOMORROW = datetime.now(timezone.utc).date() + timedelta(days=1)
SLOT = datetime(TOMORROW.year, TOMORROW.month, TOMORROW.day, 10, 0, tzinfo=timezone.utc)
PRICE = 50_000


@pytest.fixture(autouse=True)
def console_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_service, "get_email_provider", lambda: ConsoleEmailProvider())


@pytest.fixture
def db(client: TestClient) -> Generator[Session, None, None]:
    sessions = app.dependency_overrides[get_db]()
    session = next(sessions)
    try:
        yield session
    finally:
        session.close()


def _host(client: TestClient, *, with_payouts: bool = True) -> str:
    client.post(f"{API}/auth/register", json={"full_name": "Avery Stone", "email": "avery@example.com", "password": "strong-password"})
    client.patch(f"{API}/users/me", json={"username": "avery", "timezone": "UTC"})
    hours = [{"weekday": day, "start_time": "09:00", "end_time": "17:00", "is_enabled": True, "breaks": []} for day in range(7)]
    assert client.put(f"{API}/availability", json={"working_hours": hours}).status_code == 200
    event = client.post(
        f"{API}/event-types",
        json={"title": "Advisory call", "duration_minutes": 30, "slot_interval_minutes": 30, "price_minor": PRICE, "currency": "INR"},
    )
    assert event.status_code == 201, event.text
    if with_payouts:
        assert client.post(f"{API}/payments/account", json=ACCOUNT_PAYLOAD).status_code == 201
    return str(event.json()["slug"])


def _book(client: TestClient, slug: str, starts_at: datetime = SLOT) -> Any:
    return client.post(
        f"{API}/public/avery/{slug}/bookings",
        json={"starts_at": starts_at.isoformat(), "invitee_name": "Jamie Doe", "invitee_email": "jamie@example.com", "invitee_timezone": "UTC"},
    )


def _webhook(client: TestClient, payload: dict[str, Any], event_id: str, *, signature: str | None = None) -> Any:
    body = json.dumps(payload).encode()
    return client.post(
        f"{API}/webhooks/razorpay",
        content=body,
        headers={
            "content-type": "application/json",
            "x-razorpay-signature": signature if signature is not None else sign_webhook(body),
            "x-razorpay-event-id": event_id,
        },
    )


def _captured(order_id: str, payment_id: str = "pay_Test1", amount: int = PRICE) -> dict[str, Any]:
    return {
        "entity": "event",
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": payment_id, "order_id": order_id, "amount": amount, "status": "captured", "notes": []}}},
    }


def _order_paid(order_id: str, booking_id: str, payment_id: str = "pay_Test1") -> dict[str, Any]:
    return {
        "entity": "event",
        "event": "order.paid",
        "payload": {
            "payment": {"entity": {"id": payment_id, "order_id": order_id, "amount": PRICE}},
            "order": {"entity": {"id": order_id, "amount_paid": PRICE, "notes": {"booking_id": booking_id}}},
        },
    }


# Commission -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "bps", "commission"),
    [
        (50_000, 1000, 5_000),
        (50_000, 250, 1_250),
        (999, 125, 12),  # 12.4875 rounds down
        (1, 5000, 1),  # 0.5 rounds half-up
        (199, 250, 5),  # 4.975 rounds up
        (12_345, 0, 0),
        (12_345, 10_000, 12_345),
        (0, 1000, 0),
    ],
)
def test_commission_split_rounds_half_up(amount: int, bps: int, commission: int) -> None:
    split = split_payment(amount, bps)
    assert split.platform_commission_minor == commission
    assert split.host_share_minor == amount - commission


def test_commission_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        split_payment(100, 10_001)
    with pytest.raises(ValueError):
        split_payment(-1, 100)


# Booking gate ----------------------------------------------------------------


def test_paid_booking_requires_active_payouts(client: TestClient, razorpay: FakeRazorpay) -> None:  # noqa: F811
    slug = _host(client, with_payouts=False)
    blocked = _book(client, slug)

    razorpay.activation_status = "under_review"
    client.post(f"{API}/payments/account", json=ACCOUNT_PAYLOAD)
    still_blocked = _book(client, slug)

    razorpay.activation_status = "activated"
    client.post(f"{API}/payments/account/sync")
    allowed = _book(client, slug)

    assert blocked.status_code == 409
    assert blocked.json()["code"] == "host_payments_not_ready"
    assert still_blocked.json()["code"] == "host_payments_not_ready"
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["status"] == "pending"


# Checkout --------------------------------------------------------------------


def test_checkout_creates_order_with_route_transfer(client: TestClient, razorpay: FakeRazorpay) -> None:  # noqa: F811
    slug = _host(client)
    booking = _book(client, slug).json()

    checkout = client.post(f"{API}/payments/bookings/{booking['id']}/checkout")
    again = client.post(f"{API}/payments/bookings/{booking['id']}/checkout")

    assert checkout.status_code == 200, checkout.text
    assert checkout.json() == {
        "provider": "razorpay",
        "booking_id": booking["id"],
        "key_id": KEY_ID,
        "order_id": "order_Test1",
        "amount": PRICE,
        "currency": "INR",
        "name": "Avery Stone",
        "description": "Advisory call",
        "prefill": {"name": "Jamie Doe", "email": "jamie@example.com"},
    }
    order = razorpay.body("POST", "/v1/orders")
    assert order["amount"] == PRICE
    assert order["currency"] == "INR"
    assert order["receipt"] == booking["id"]
    assert order["notes"]["booking_id"] == booking["id"]
    # 10% platform commission stays with the platform; the rest goes to the host.
    assert order["transfers"] == [
        {
            "account": ACCOUNT_ID,
            "amount": 45_000,
            "currency": "INR",
            "notes": {"booking_id": booking["id"]},
            "linked_account_notes": ["booking_id"],
            "on_hold": False,
        }
    ]
    # The order is reused rather than recreated.
    assert again.json()["order_id"] == "order_Test1"
    assert razorpay.order_count == 1


def test_checkout_after_payment_window_returns_410(client: TestClient, razorpay: FakeRazorpay, db: Session) -> None:  # noqa: F811
    slug = _host(client)
    booking_id = _book(client, slug).json()["id"]
    booking = db.get(Booking, uuid.UUID(booking_id))
    assert booking is not None
    booking.payment_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    response = client.post(f"{API}/payments/bookings/{booking_id}/checkout")

    assert response.status_code == 410
    assert response.json()["code"] == "payment_window_expired"
    assert razorpay.order_count == 0


# Webhooks --------------------------------------------------------------------


def test_webhook_signature_confirmation_and_idempotency(client: TestClient, razorpay: FakeRazorpay) -> None:  # noqa: F811
    slug = _host(client)
    booking_id = _book(client, slug).json()["id"]
    order_id = client.post(f"{API}/payments/bookings/{booking_id}/checkout").json()["order_id"]

    forged = _webhook(client, _captured(order_id), "evt_1", signature="bad")
    first = _webhook(client, _captured(order_id), "evt_1")
    replay = _webhook(client, _captured(order_id), "evt_1")
    order_paid = _webhook(client, _order_paid(order_id, booking_id), "evt_2")

    assert forged.status_code == 401
    assert first.status_code == 202, first.text
    assert first.json() == {"status": "processed"}
    assert replay.json() == {"status": "duplicate"}
    assert order_paid.json() == {"status": "duplicate"}
    assert razorpay.refund_count == 0


def test_webhook_confirms_booking_and_amount_must_match(client: TestClient, razorpay: FakeRazorpay, db: Session) -> None:  # noqa: F811
    slug = _host(client)
    booking_id = _book(client, slug).json()["id"]
    order_id = client.post(f"{API}/payments/bookings/{booking_id}/checkout").json()["order_id"]

    mismatch = _webhook(client, _captured(order_id, amount=PRICE - 1), "evt_bad_amount")
    paid = _webhook(client, _order_paid(order_id, booking_id), "evt_paid")

    booking = db.get(Booking, uuid.UUID(booking_id))
    assert booking is not None
    db.refresh(booking)
    assert mismatch.status_code == 409
    assert paid.json() == {"status": "processed"}
    assert booking.status == BookingStatus.CONFIRMED
    assert booking.provider_payment_id == "pay_Test1"
    assert booking.provider_order_id == order_id
    assert booking.platform_commission_minor == 5_000


def test_late_payment_for_taken_slot_is_refunded(client: TestClient, razorpay: FakeRazorpay, db: Session) -> None:  # noqa: F811
    slug = _host(client)
    booking_id = _book(client, slug).json()["id"]
    order_id = client.post(f"{API}/payments/bookings/{booking_id}/checkout").json()["order_id"]
    # The payment window lapses and someone else books the same slot.
    late = db.get(Booking, uuid.UUID(booking_id))
    assert late is not None
    late.status = BookingStatus.EXPIRED
    db.add(
        Booking(
            host_id=late.host_id, event_type_id=late.event_type_id, invitee_name="Other", invitee_email="other@example.com",
            invitee_timezone="UTC", starts_at=late.starts_at, ends_at=late.ends_at, status=BookingStatus.CONFIRMED,
            booking_amount=PRICE, payment_expires_at=late.payment_expires_at,
        )
    )
    db.commit()

    first = _webhook(client, _captured(order_id), "evt_late_1")
    second = _webhook(client, _order_paid(order_id, booking_id), "evt_late_2")

    db.refresh(late)
    assert first.status_code == 202, first.text
    assert first.json() == {"status": "refunded"}
    assert second.json() == {"status": "refunded"}
    assert razorpay.refund_count == 1
    refund = razorpay.body("POST", "/v1/payments/pay_Test1/refund")
    assert refund["amount"] == PRICE
    assert refund["reverse_all"] is True
    assert late.status == BookingStatus.EXPIRED
    assert late.refund_id == "rfnd_Test1"
    assert late.refund_status == "processed"
    assert late.refunded_at is not None

    refund_update = _webhook(
        client,
        {"event": "refund.failed", "payload": {"refund": {"entity": {"id": "rfnd_Test1", "status": "failed"}}}},
        "evt_refund",
    )
    db.refresh(late)
    assert refund_update.json() == {"status": "processed"}
    assert late.refund_status == "failed"


def test_expired_booking_paid_while_slot_free_is_confirmed(client: TestClient, razorpay: FakeRazorpay, db: Session) -> None:  # noqa: F811
    slug = _host(client)
    booking_id = _book(client, slug).json()["id"]
    order_id = client.post(f"{API}/payments/bookings/{booking_id}/checkout").json()["order_id"]
    booking = db.get(Booking, uuid.UUID(booking_id))
    assert booking is not None
    booking.status = BookingStatus.EXPIRED
    db.commit()

    response = _webhook(client, _captured(order_id), "evt_free")

    db.refresh(booking)
    assert response.json() == {"status": "processed"}
    assert booking.status == BookingStatus.CONFIRMED
    assert razorpay.refund_count == 0


def test_route_activation_webhook_updates_host(client: TestClient, razorpay: FakeRazorpay) -> None:  # noqa: F811
    razorpay.activation_status = "under_review"
    _host(client)

    needs = _webhook(
        client,
        {
            "entity": "event",
            "account_id": ACCOUNT_ID,
            "event": "product.route.needs_clarification",
            "payload": {
                "merchant_product": {
                    "entity": {"id": "acc_prd_TestProd01", "activation_status": "needs_clarification"},
                    "data": {"requirements": [{"field_reference": "settlements.ifsc_code", "reason_code": "needs_clarification", "status": "required", "description": "Check the IFSC."}]},
                }
            },
        },
        "evt_product_1",
    )
    after_needs = client.get(f"{API}/payments/account").json()
    activated = _webhook(
        client,
        {
            "entity": "event",
            "account_id": ACCOUNT_ID,
            "event": "product.route.activated",
            "payload": {"merchant_product": {"entity": {"id": "acc_prd_TestProd01", "activation_status": "activated"}, "data": []}},
        },
        "evt_product_2",
    )
    after_activation = client.get(f"{API}/payments/account").json()

    assert needs.json() == {"status": "processed"}
    assert after_needs["activation_status"] == "needs_clarification"
    assert after_needs["requirements"][0]["description"] == "Check the IFSC."
    assert activated.json() == {"status": "processed"}
    assert after_activation["payouts_enabled"] is True
    assert after_activation["requirements"] == []


# Client-side verification ----------------------------------------------------


def test_checkout_signature_verification_confirms_booking(client: TestClient, razorpay: FakeRazorpay) -> None:  # noqa: F811
    slug = _host(client)
    booking_id = _book(client, slug).json()["id"]
    order_id = client.post(f"{API}/payments/bookings/{booking_id}/checkout").json()["order_id"]

    forged = client.post(
        f"{API}/payments/bookings/{booking_id}/verify",
        json={"razorpay_order_id": order_id, "razorpay_payment_id": "pay_Test1", "razorpay_signature": "forged"},
    )
    verified = client.post(
        f"{API}/payments/bookings/{booking_id}/verify",
        json={"razorpay_order_id": order_id, "razorpay_payment_id": "pay_Test1", "razorpay_signature": sign_checkout(order_id, "pay_Test1")},
    )
    webhook = _webhook(client, _captured(order_id), "evt_after_verify")

    assert forged.status_code == 400
    assert verified.status_code == 200, verified.text
    assert verified.json() == {"booking_id": booking_id, "status": "confirmed"}
    assert webhook.json() == {"status": "duplicate"}


# Refunds ---------------------------------------------------------------------


def test_refund_booking_is_idempotent_and_reports_failures(client: TestClient, razorpay: FakeRazorpay, db: Session) -> None:  # noqa: F811
    slug = _host(client)
    booking_id = _book(client, slug).json()["id"]
    order_id = client.post(f"{API}/payments/bookings/{booking_id}/checkout").json()["order_id"]
    _webhook(client, _captured(order_id, payment_id="pay_Refund"), "evt_paid")
    booking = db.get(Booking, uuid.UUID(booking_id))
    assert booking is not None
    db.refresh(booking)

    razorpay.failures[("POST", "/v1/payments/pay_Refund/refund")] = (400, "The payment has been fully refunded already")
    with pytest.raises(AppError) as failure:
        RefundService(db).refund_booking(booking, "cancelled_by_host")
    RefundService(db).refund_booking(booking, "cancelled_by_host")
    RefundService(db).refund_booking(booking, "cancelled_by_host")

    assert failure.value.code == "refund_failed"
    assert razorpay.refund_count == 1
    assert booking.refund_id == "rfnd_Test1"
    assert razorpay.body("POST", "/v1/payments/pay_Refund/refund")["notes"] == {"booking_id": booking_id, "reason": "cancelled_by_host"}


def test_refund_is_a_no_op_without_a_payment(client: TestClient, razorpay: FakeRazorpay, db: Session) -> None:  # noqa: F811
    slug = _host(client)
    booking_id = _book(client, slug).json()["id"]
    booking = db.get(Booking, uuid.UUID(booking_id))
    assert booking is not None

    RefundService(db).refund_booking(booking, "cancelled")

    assert booking.refund_id is None
    assert razorpay.refund_count == 0
