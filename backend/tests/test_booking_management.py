import uuid
from collections.abc import Generator, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.events import BOOKING_CANCELLED, BOOKING_CONFIRMED, BOOKING_RESCHEDULED, DomainEvent, event_bus
from app.domains.bookings.models import Booking
from app.domains.email import service as email_service
from app.domains.email.providers import EmailAttachment, EmailProvider
from app.domains.email.service import EmailService
from app.domains.notifications.formatting import format_amount, format_when
from app.domains.notifications.ics import CalendarEvent, CalendarMethod, build_ics, escape_text, fold_line
from app.domains.notifications.models import BookingReminder
from app.domains.notifications.service import BookingReminderService
from app.main import app
from tests.razorpay_fakes import FakeRazorpay, razorpay, sign_checkout  # noqa: F401
from tests.test_razorpay_payments import PRICE, _captured, _webhook


API = "/api/v1"
IN_THREE_DAYS = datetime.now(timezone.utc).date() + timedelta(days=3)
SLOT = datetime(IN_THREE_DAYS.year, IN_THREE_DAYS.month, IN_THREE_DAYS.day, 10, 0, tzinfo=timezone.utc)


class RecordingEmailProvider(EmailProvider):
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send(
        self,
        *,
        recipient: str,
        subject: str,
        text: str,
        html: str | None = None,
        attachments: Sequence[EmailAttachment] = (),
    ) -> None:
        self.sent.append({"recipient": recipient, "subject": subject, "text": text, "html": html, "attachments": list(attachments)})

    def to(self, recipient: str) -> list[dict[str, Any]]:
        return [email for email in self.sent if email["recipient"] == recipient]

    def ics(self, email: dict[str, Any]) -> str:
        attachment = next(item for item in email["attachments"] if item.mime_type == "text/calendar")
        return str(attachment.content.decode())


@pytest.fixture(autouse=True)
def emails(monkeypatch: pytest.MonkeyPatch) -> RecordingEmailProvider:
    provider = RecordingEmailProvider()
    monkeypatch.setattr(email_service, "get_email_provider", lambda: provider)
    return provider


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> list[DomainEvent]:
    published: list[DomainEvent] = []
    original = event_bus.publish

    def record(event: DomainEvent) -> None:
        published.append(event)
        original(event)

    monkeypatch.setattr(event_bus, "publish", record)
    return published


@pytest.fixture
def db(client: TestClient) -> Generator[Session, None, None]:
    sessions = app.dependency_overrides[get_db]()
    session = next(sessions)
    try:
        yield session
    finally:
        session.close()


def _register(client: TestClient, email: str = "avery@example.com", username: str = "avery", tz: str = "UTC") -> None:
    client.post(f"{API}/auth/register", json={"full_name": "Avery Stone", "email": email, "password": "strong-password"})
    assert client.patch(f"{API}/users/me", json={"username": username, "timezone": tz}).status_code == 200
    hours = [{"weekday": day, "start_time": "09:00", "end_time": "17:00", "is_enabled": True, "breaks": []} for day in range(7)]
    assert client.put(f"{API}/availability", json={"working_hours": hours}).status_code == 200


def _free_event(client: TestClient, **rules: Any) -> dict[str, Any]:
    response = client.post(
        f"{API}/event-types",
        json={"title": "Intro call", "duration_minutes": 30, "slot_interval_minutes": 30, "price_minor": 0, "currency": "INR", **rules},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def _paid_event(client: TestClient) -> dict[str, Any]:
    from tests.razorpay_fakes import ACCOUNT_PAYLOAD

    response = client.post(
        f"{API}/event-types",
        json={"title": "Advisory call", "duration_minutes": 30, "slot_interval_minutes": 30, "price_minor": PRICE, "currency": "INR"},
    )
    assert response.status_code == 201, response.text
    assert client.post(f"{API}/payments/account", json=ACCOUNT_PAYLOAD).status_code == 201
    return dict(response.json())


def _book(client: TestClient, slug: str, starts_at: datetime = SLOT, username: str = "avery", tz: str = "Asia/Kolkata") -> dict[str, Any]:
    response = client.post(
        f"{API}/public/{username}/{slug}/bookings",
        json={
            "starts_at": starts_at.isoformat(),
            "invitee_name": "Jamie Doe",
            "invitee_email": "jamie@example.com",
            "invitee_timezone": tz,
            "notes": "Discuss pricing, roadmap; and next steps",
        },
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def _pay(client: TestClient, booking_id: str) -> str:
    order_id = str(client.post(f"{API}/payments/bookings/{booking_id}/checkout").json()["order_id"])
    assert _webhook(client, _captured(order_id), f"evt_{booking_id}").json() == {"status": "processed"}
    return order_id


def _token(emails: RecordingEmailProvider) -> str:
    text = emails.to("jamie@example.com")[-1]["text"]
    link = next(word for word in text.split() if "/bookings/manage/" in word)
    return parse_qs(urlparse(link).query)["token"][0]


def _parse(value: str) -> datetime:
    # Python 3.10's fromisoformat does not accept a trailing "Z".
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _confirmed(events: list[DomainEvent]) -> list[DomainEvent]:
    return [event for event in events if event.name == BOOKING_CONFIRMED]


# Event publication -----------------------------------------------------------


def test_free_booking_publishes_confirmed_once_and_emails_both_parties(
    client: TestClient, emails: RecordingEmailProvider, events: list[DomainEvent]
) -> None:
    _register(client)
    event = _free_event(client)
    booking = _book(client, event["slug"])

    assert [item.payload for item in _confirmed(events)] == [{"booking_id": booking["id"]}]
    invitee = emails.to("jamie@example.com")
    host = emails.to("avery@example.com")
    assert len(invitee) == 1 and len(host) == 1
    # Times are shown in each recipient's own timezone.
    assert "3:30 PM – 4:00 PM (Asia/Kolkata, GMT+5:30)" in invitee[0]["text"]
    assert "10:00 AM – 10:30 AM (UTC, GMT)" in host[0]["text"]
    assert invitee[0]["subject"].startswith("Confirmed: Intro call with Avery Stone")
    assert host[0]["subject"].startswith("New booking: Jamie Doe")
    assert f"/bookings/manage/{booking['id']}?token=" in invitee[0]["text"]
    assert "/bookings/manage/" not in host[0]["text"]
    assert "Discuss pricing" in invitee[0]["html"] and "<table" in invitee[0]["html"]
    ics = emails.ics(invitee[0])
    assert "METHOD:REQUEST\r\n" in ics
    assert f"UID:{booking['id']}@threecal.com\r\n" in ics
    assert "SEQUENCE:0\r\n" in ics
    assert "DTSTART:" + SLOT.strftime("%Y%m%dT%H%M%SZ") in ics


def test_paid_booking_publishes_confirmed_once_via_webhook(
    client: TestClient, razorpay: FakeRazorpay, emails: RecordingEmailProvider, events: list[DomainEvent]  # noqa: F811
) -> None:
    _register(client)
    event = _paid_event(client)
    booking = _book(client, event["slug"])
    assert _confirmed(events) == []
    assert emails.sent == []

    order_id = _pay(client, booking["id"])
    duplicate = _webhook(client, _captured(order_id), "evt_again")

    assert duplicate.json() == {"status": "duplicate"}
    assert [item.payload for item in _confirmed(events)] == [{"booking_id": booking["id"]}]
    invitee = emails.to("jamie@example.com")
    assert len(invitee) == 1
    assert "Amount paid" in invitee[0]["text"] and "₹500.00" in invitee[0]["text"]


def test_paid_booking_publishes_confirmed_once_via_verify_then_webhook(
    client: TestClient, razorpay: FakeRazorpay, events: list[DomainEvent]  # noqa: F811
) -> None:
    _register(client)
    event = _paid_event(client)
    booking_id = _book(client, event["slug"])["id"]
    order_id = client.post(f"{API}/payments/bookings/{booking_id}/checkout").json()["order_id"]

    verified = client.post(
        f"{API}/payments/bookings/{booking_id}/verify",
        json={"razorpay_order_id": order_id, "razorpay_payment_id": "pay_Test1", "razorpay_signature": sign_checkout(order_id, "pay_Test1")},
    )
    webhook = _webhook(client, _captured(order_id), "evt_after_verify")
    again = client.post(
        f"{API}/payments/bookings/{booking_id}/verify",
        json={"razorpay_order_id": order_id, "razorpay_payment_id": "pay_Test1", "razorpay_signature": sign_checkout(order_id, "pay_Test1")},
    )

    assert verified.status_code == 200 and again.status_code == 200
    assert webhook.json() == {"status": "duplicate"}
    assert len(_confirmed(events)) == 1


# Host management -------------------------------------------------------------


def test_host_lists_bookings_by_scope_and_event_type(client: TestClient) -> None:
    _register(client)
    first = _free_event(client)
    second = _free_event(client, title="Deep dive", duration_minutes=60)
    upcoming = _book(client, first["slug"])
    other = _book(client, second["slug"], SLOT + timedelta(hours=2))
    cancelled = _book(client, first["slug"], SLOT + timedelta(days=1))
    assert client.post(f"{API}/bookings/{cancelled['id']}/cancel", json={}).status_code == 200

    page = client.get(f"{API}/bookings", params={"scope": "upcoming"}).json()
    filtered = client.get(f"{API}/bookings", params={"scope": "upcoming", "event_type_id": second["id"]}).json()
    limited = client.get(f"{API}/bookings", params={"scope": "upcoming", "limit": 1, "offset": 1}).json()
    cancelled_page = client.get(f"{API}/bookings", params={"scope": "cancelled"}).json()
    past = client.get(f"{API}/bookings", params={"scope": "past"}).json()

    assert [item["id"] for item in page["items"]] == [upcoming["id"], other["id"]]
    assert page["total"] == 2
    assert page["items"][0]["event_type_title"] == "Intro call"
    assert page["items"][0]["starts_at"].endswith("+00:00") or page["items"][0]["starts_at"].endswith("Z")
    assert [item["id"] for item in filtered["items"]] == [other["id"]]
    assert limited["total"] == 2 and [item["id"] for item in limited["items"]] == [other["id"]]
    assert [item["id"] for item in cancelled_page["items"]] == [cancelled["id"]]
    assert cancelled_page["items"][0]["cancelled_by"] == "host"
    assert past["items"] == []
    assert client.get(f"{API}/bookings/{upcoming['id']}").json()["notes"].startswith("Discuss")


def test_host_cannot_see_or_change_other_hosts_bookings(client: TestClient) -> None:
    _register(client)
    event = _free_event(client)
    booking = _book(client, event["slug"])
    client.post(f"{API}/auth/logout")
    _register(client, email="other@example.com", username="other")

    assert client.get(f"{API}/bookings/{booking['id']}").status_code == 404
    assert client.post(f"{API}/bookings/{booking['id']}/cancel", json={}).status_code == 404
    assert client.post(f"{API}/bookings/{booking['id']}/reschedule", json={"starts_at": SLOT.isoformat()}).status_code == 404
    assert client.get(f"{API}/bookings", params={"scope": "upcoming"}).json()["total"] == 0


def test_host_cancel_of_paid_booking_refunds_and_notifies(
    client: TestClient, razorpay: FakeRazorpay, emails: RecordingEmailProvider, events: list[DomainEvent], db: Session  # noqa: F811
) -> None:
    _register(client)
    event = _paid_event(client)
    booking = _book(client, event["slug"])
    _pay(client, booking["id"])
    emails.sent.clear()

    cancelled = client.post(f"{API}/bookings/{booking['id']}/cancel", json={"reason": "Travelling, sorry"})
    again = client.post(f"{API}/bookings/{booking['id']}/cancel", json={})

    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()
    assert body["status"] == "cancelled" and body["cancelled_by"] == "host"
    assert body["cancellation_reason"] == "Travelling, sorry"
    assert body["refund_status"] is not None
    assert razorpay.refund_count == 1
    assert again.status_code == 409
    cancel_events = [item for item in events if item.name == BOOKING_CANCELLED]
    assert [item.payload for item in cancel_events] == [{"booking_id": booking["id"], "cancelled_by": "host", "reason": "Travelling, sorry"}]
    invitee = emails.to("jamie@example.com")[0]
    assert "Avery Stone cancelled this booking." in invitee["text"]
    assert "full refund of ₹500.00" in invitee["text"]
    assert "You cancelled this booking." in emails.to("avery@example.com")[0]["text"]
    ics = emails.ics(invitee)
    assert "METHOD:CANCEL\r\n" in ics and "SEQUENCE:1\r\n" in ics and "STATUS:CANCELLED\r\n" in ics
    assert f"UID:{booking['id']}@threecal.com" in ics


def test_host_reschedule_moves_booking_in_place(
    client: TestClient, emails: RecordingEmailProvider, events: list[DomainEvent]
) -> None:
    _register(client)
    # A daily limit of one means the booking's own slot must not count against its new time.
    event = _free_event(client, daily_booking_limit=1)
    booking = _book(client, event["slug"])
    emails.sent.clear()
    new_start = SLOT + timedelta(hours=3)

    slots = client.get(f"{API}/bookings/{booking['id']}/slots", params={"start": SLOT.date().isoformat(), "end": SLOT.date().isoformat(), "timezone": "UTC"})
    outside_hours = client.post(f"{API}/bookings/{booking['id']}/reschedule", json={"starts_at": (SLOT + timedelta(hours=12)).isoformat()})
    moved = client.post(f"{API}/bookings/{booking['id']}/reschedule", json={"starts_at": new_start.isoformat()})

    assert slots.status_code == 200
    starts = {_parse(slot["starts_at"]) for slot in slots.json()}
    assert new_start in starts and SLOT not in starts
    assert outside_hours.status_code == 409
    assert moved.status_code == 200, moved.text
    assert moved.json()["id"] == booking["id"]
    assert _parse(moved.json()["starts_at"]) == new_start
    rescheduled = [item for item in events if item.name == BOOKING_RESCHEDULED]
    assert len(rescheduled) == 1
    assert _parse(rescheduled[0].payload["previous_starts_at"]) == SLOT
    invitee = emails.to("jamie@example.com")[0]
    assert invitee["subject"].startswith("Rescheduled:")
    assert "Previous time" in invitee["text"]
    ics = emails.ics(invitee)
    assert "METHOD:REQUEST\r\n" in ics and "SEQUENCE:1\r\n" in ics


# Invitee self-service ----------------------------------------------------------


def test_invitee_can_view_and_cancel_with_token_and_gets_refund(
    client: TestClient, razorpay: FakeRazorpay, emails: RecordingEmailProvider, db: Session  # noqa: F811
) -> None:
    _register(client)
    event = _paid_event(client)
    booking = _book(client, event["slug"])
    _pay(client, booking["id"])
    token = _token(emails)
    client.post(f"{API}/auth/logout")

    wrong = client.get(f"{API}/public/bookings/{booking['id']}", params={"token": token[:-2] + "xx"})
    unknown = client.get(f"{API}/public/bookings/{uuid.uuid4()}", params={"token": token})
    view = client.get(f"{API}/public/bookings/{booking['id']}", params={"token": token})
    bad_cancel = client.post(f"{API}/public/bookings/{booking['id']}/cancel", json={"token": "nope"})
    cancelled = client.post(f"{API}/public/bookings/{booking['id']}/cancel", json={"token": token, "reason": "Conflict"})

    assert wrong.status_code == 404 and unknown.status_code == 404 and bad_cancel.status_code == 404
    assert view.status_code == 200, view.text
    assert view.json()["can_cancel"] is True and view.json()["host_name"] == "Avery Stone"
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled" and cancelled.json()["cancelled_by"] == "invitee"
    assert razorpay.refund_count == 1
    host_email = emails.to("avery@example.com")[-1]
    assert "Jamie Doe cancelled this booking." in host_email["text"]
    assert "has been refunded ₹500.00 in full" in host_email["text"]
    stored = db.get(Booking, uuid.UUID(booking["id"]))
    assert stored is not None and stored.manage_token_hash and token not in stored.manage_token_hash


def test_invitee_changes_are_blocked_after_the_cutoff(
    client: TestClient, emails: RecordingEmailProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    _register(client)
    event = _free_event(client)
    booking = _book(client, event["slug"])
    token = _token(emails)
    # The booking starts in ~3 days, so a 5-day cutoff has already passed.
    monkeypatch.setattr(settings, "invitee_change_cutoff_hours", 24 * 5)

    view = client.get(f"{API}/public/bookings/{booking['id']}", params={"token": token})
    cancel = client.post(f"{API}/public/bookings/{booking['id']}/cancel", json={"token": token})
    reschedule = client.post(
        f"{API}/public/bookings/{booking['id']}/reschedule",
        json={"token": token, "starts_at": (SLOT + timedelta(hours=1)).isoformat()},
    )

    assert view.status_code == 200
    assert view.json()["can_cancel"] is False and view.json()["can_reschedule"] is False
    assert cancel.status_code == 409 and cancel.json()["code"] == "change_window_closed"
    assert reschedule.status_code == 409 and reschedule.json()["code"] == "change_window_closed"


def test_invitee_can_reschedule_with_token(client: TestClient, emails: RecordingEmailProvider) -> None:
    _register(client)
    event = _free_event(client)
    booking = _book(client, event["slug"])
    token = _token(emails)
    new_start = SLOT + timedelta(hours=1)

    slots = client.get(
        f"{API}/public/bookings/{booking['id']}/slots",
        params={"token": token, "start": SLOT.date().isoformat(), "end": SLOT.date().isoformat(), "timezone": "UTC"},
    )
    moved = client.post(f"{API}/public/bookings/{booking['id']}/reschedule", json={"token": token, "starts_at": new_start.isoformat()})

    assert slots.status_code == 200 and slots.json()
    assert moved.status_code == 200, moved.text
    assert _parse(moved.json()["starts_at"]) == new_start
    assert "You moved this booking to a new time." in emails.to("jamie@example.com")[-1]["text"]
    assert "Jamie Doe moved this booking to a new time." in emails.to("avery@example.com")[-1]["text"]
    # The manage link keeps working after a reschedule.
    assert client.get(f"{API}/public/bookings/{booking['id']}", params={"token": token}).status_code == 200


def test_invitee_endpoints_are_rate_limited(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    booking_id = uuid.uuid4()
    statuses = [client.post(f"{API}/public/bookings/{booking_id}/cancel", json={"token": "x"}).status_code for _ in range(11)]
    assert statuses[:10] == [404] * 10
    assert statuses[10] == 429


# Reminders ----------------------------------------------------------------------


def _reminders(db: Session, emails: RecordingEmailProvider, now: datetime) -> BookingReminderService:
    return BookingReminderService(db, EmailService(emails), offsets_minutes=[1440, 60], grace_minutes=30, clock=lambda: now)


def test_reminders_send_once_per_offset_and_skip_missed_windows(
    client: TestClient, emails: RecordingEmailProvider, db: Session
) -> None:
    _register(client)
    event = _free_event(client)
    _book(client, event["slug"])
    emails.sent.clear()

    # Two hours before the start the 24h reminder window was missed, and the 1h one is not due yet.
    assert _reminders(db, emails, SLOT - timedelta(hours=2)).send_due() == 0
    # Five minutes into the 24h window: sent once, even if the job runs again (or overlaps).
    assert _reminders(db, emails, SLOT - timedelta(hours=24) + timedelta(minutes=5)).send_due() == 1
    assert _reminders(db, emails, SLOT - timedelta(hours=24) + timedelta(minutes=10)).send_due() == 0
    # Missed by more than the grace period: skipped.
    assert _reminders(db, emails, SLOT - timedelta(minutes=60) + timedelta(minutes=45)).send_due() == 0
    assert _reminders(db, emails, SLOT - timedelta(minutes=55)).send_due() == 1

    subjects = [email["subject"] for email in emails.to("jamie@example.com")]
    assert subjects == ["Reminder: Intro call with Avery Stone in 24 hours", "Reminder: Intro call with Avery Stone in 1 hour"]
    assert len(emails.to("avery@example.com")) == 2
    assert db.scalar(select(func.count()).select_from(BookingReminder)) == 2


def test_reminders_skip_cancelled_and_rearm_after_reschedule(
    client: TestClient, emails: RecordingEmailProvider, db: Session
) -> None:
    _register(client)
    event = _free_event(client)
    drop = _book(client, event["slug"])
    client.post(f"{API}/bookings/{drop['id']}/cancel", json={})
    keep = _book(client, event["slug"])
    emails.sent.clear()

    assert _reminders(db, emails, SLOT - timedelta(hours=23, minutes=55)).send_due() == 1
    assert db.scalar(select(func.count()).select_from(BookingReminder)) == 1

    client.post(f"{API}/bookings/{keep['id']}/reschedule", json={"starts_at": (SLOT + timedelta(hours=2)).isoformat()})
    assert db.scalar(select(func.count()).select_from(BookingReminder)) == 0


def test_claiming_a_reminder_twice_fails(client: TestClient, emails: RecordingEmailProvider, db: Session) -> None:
    from app.domains.notifications.repository import BookingReminderRepository

    _register(client)
    booking = _book(client, _free_event(client)["slug"])
    repository = BookingReminderRepository(db)
    now = datetime.now(timezone.utc)

    assert repository.claim(uuid.UUID(booking["id"]), 60, now) is True
    assert repository.claim(uuid.UUID(booking["id"]), 60, now) is False


def test_account_deletion_removes_reminders(client: TestClient, emails: RecordingEmailProvider, db: Session) -> None:
    _register(client)
    booking = _book(client, _free_event(client)["slug"])
    db.add(BookingReminder(booking_id=uuid.UUID(booking["id"]), offset_minutes=60))
    db.commit()
    client.post(f"{API}/bookings/{booking['id']}/cancel", json={})

    deleted = client.request("DELETE", f"{API}/users/me", json={"password": "strong-password"})

    assert deleted.status_code == 204, deleted.text
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(BookingReminder)) == 0


# Email building blocks ------------------------------------------------------------


def test_ics_escapes_folds_and_uses_crlf() -> None:
    event = CalendarEvent(
        uid="abc@threecal.com",
        sequence=2,
        starts_at=datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 10, 14, 10, 30, tzinfo=timezone.utc),
        summary="Call; with, Jamie",
        description="Line one\nLine two with ünïcödé " + "x" * 120,
        organizer_name='Avery "AS" Stone',
        organizer_email="avery@example.com",
        attendee_name="Jamie Doe",
        attendee_email="jamie@example.com",
    )
    ics = build_ics(event, CalendarMethod.REQUEST)

    assert ics.endswith("\r\n")
    assert "\n" not in ics.replace("\r\n", "")
    for line in ics.split("\r\n"):
        assert len(line.encode()) <= 75
    unfolded = ics.replace("\r\n ", "")
    assert "SUMMARY:Call\\; with\\, Jamie\r\n" in unfolded
    assert "DESCRIPTION:Line one\\nLine two with ünïcödé " in unfolded
    assert 'ORGANIZER;CN="Avery AS Stone":mailto:avery@example.com' in unfolded
    assert "SEQUENCE:2\r\n" in unfolded and "UID:abc@threecal.com\r\n" in unfolded
    assert escape_text("a\\b") == "a\\\\b"
    assert fold_line("short") == "short"


def test_human_readable_formatting() -> None:
    starts = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)
    assert format_when(starts, starts + timedelta(minutes=45), "Asia/Kolkata") == (
        "Wednesday, 14 October 2026, 3:30 PM – 4:15 PM (Asia/Kolkata, GMT+5:30)"
    )
    assert format_when(starts, starts + timedelta(minutes=30), "America/New_York").endswith("6:00 AM – 6:30 AM (America/New_York, GMT-4)")
    assert format_amount(50_000, "INR") == "₹500.00"
    assert format_amount(1_234_500, "AED") == "AED 12,345.00"


def test_auth_emails_are_html(emails: RecordingEmailProvider) -> None:
    from app.domains.users.models import User

    user = User(email="a@example.com", full_name="A <b>")
    EmailService(emails).send_password_reset(user, "https://threecal.test/reset?token=t")

    sent = emails.sent[-1]
    assert sent["html"] and "A &lt;b&gt;" in sent["html"]
    assert 'href="https://threecal.test/reset?token=t"' in sent["html"]
    assert "https://threecal.test/reset?token=t" in sent["text"]


# Reserved usernames -----------------------------------------------------------------


@pytest.mark.parametrize("username", ["bookings", "dashboard", "login", "verify-email", "reset-password", "api"])
def test_reserved_usernames_are_rejected(client: TestClient, username: str) -> None:
    client.post(f"{API}/auth/register", json={"full_name": "Avery Stone", "email": "avery@example.com", "password": "strong-password"})
    response = client.patch(f"{API}/users/me", json={"username": username})
    assert response.status_code == 422
    assert client.patch(f"{API}/users/me", json={"username": "bookings-by-avery"}).status_code == 200
