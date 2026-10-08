from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domains.email import service as email_service
from app.domains.email.providers import ConsoleEmailProvider

API = "/api/v1"
TODAY = datetime.now(timezone.utc).date()


@pytest.fixture(autouse=True)
def console_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_service, "get_email_provider", lambda: ConsoleEmailProvider())


def _host(client: TestClient) -> None:
    client.post(f"{API}/auth/register", json={"full_name": "Avery Stone", "email": "avery@example.com", "password": "strong-password"})
    client.patch(f"{API}/users/me", json={"username": "avery", "timezone": "UTC"})
    hours = [
        {"weekday": day, "start_time": "09:00", "end_time": "17:00", "is_enabled": True, "breaks": [{"start_time": "12:00", "end_time": "13:00"}]}
        for day in range(7)
    ]
    assert client.put(f"{API}/availability", json={"working_hours": hours}).status_code == 200


def _event(client: TestClient, **rules: Any) -> dict[str, Any]:
    response = client.post(
        f"{API}/event-types",
        json={"title": "Rules call", "duration_minutes": 45, "slot_interval_minutes": 30, "price_minor": 0, **rules},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _slot_times(client: TestClient, slug: str, start: date, end: date | None = None) -> set[datetime]:
    response = client.get(f"{API}/public/avery/{slug}/slots", params={"start": start.isoformat(), "end": (end or start).isoformat(), "timezone": "UTC"})
    assert response.status_code == 200, response.text
    return {datetime.fromisoformat(slot["starts_at"].replace("Z", "+00:00")) for slot in response.json()}


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)


def _book(client: TestClient, slug: str, starts_at: datetime) -> Any:
    return client.post(
        f"{API}/public/avery/{slug}/bookings",
        json={"starts_at": starts_at.isoformat(), "invitee_name": "Jamie Doe", "invitee_email": "jamie@example.com", "invitee_timezone": "UTC"},
    )


# Date overrides --------------------------------------------------------------


def test_override_crud_and_validation(client: TestClient) -> None:
    _host(client)
    day = TODAY + timedelta(days=3)
    url = f"{API}/availability/overrides/{day.isoformat()}"

    blocked = client.put(url, json={"is_available": False, "start_time": "10:00", "end_time": "11:00"})
    assert blocked.status_code == 200
    assert blocked.json()["start_time"] is None

    custom = client.put(url, json={"is_available": True, "start_time": "10:00", "end_time": "12:00", "note": "Late start"})
    assert custom.status_code == 200
    listed = client.get(f"{API}/availability/overrides").json()
    assert len(listed) == 1
    assert listed[0]["exception_date"] == day.isoformat()
    assert listed[0]["is_available"] is True
    assert listed[0]["note"] == "Late start"

    outside = client.get(f"{API}/availability/overrides", params={"start": (day + timedelta(days=1)).isoformat()})
    assert outside.json() == []

    assert client.put(url, json={"is_available": True, "start_time": "12:00", "end_time": "11:00"}).status_code == 422
    assert client.put(url, json={"is_available": True}).status_code == 422
    past = client.put(f"{API}/availability/overrides/{(TODAY - timedelta(days=2)).isoformat()}", json={"is_available": False})
    assert past.status_code == 422
    assert past.json()["code"] == "override_in_past"
    bad_range = client.get(f"{API}/availability/overrides", params={"start": day.isoformat(), "end": (day - timedelta(days=1)).isoformat()})
    assert bad_range.status_code == 422

    assert client.delete(url).status_code == 204
    assert client.get(f"{API}/availability/overrides").json() == []
    missing = client.delete(url)
    assert missing.status_code == 404
    assert missing.json()["code"] == "override_not_found"


def test_overrides_require_authentication(client: TestClient) -> None:
    assert client.get(f"{API}/availability/overrides").status_code == 401


def test_slots_honour_overrides(client: TestClient) -> None:
    _host(client)
    event = _event(client, duration_minutes=30)
    blocked_day = TODAY + timedelta(days=2)
    custom_day = TODAY + timedelta(days=3)

    client.put(f"{API}/availability/overrides/{blocked_day.isoformat()}", json={"is_available": False})
    assert _slot_times(client, event["slug"], blocked_day) == set()
    assert _book(client, event["slug"], _at(blocked_day, 9)).status_code == 409

    # Custom hours replace weekly hours, and weekly breaks (12:00-13:00) do not apply.
    client.put(f"{API}/availability/overrides/{custom_day.isoformat()}", json={"is_available": True, "start_time": "11:30", "end_time": "13:00"})
    assert _slot_times(client, event["slug"], custom_day) == {_at(custom_day, 11, 30), _at(custom_day, 12), _at(custom_day, 12, 30)}
    assert _book(client, event["slug"], _at(custom_day, 9)).status_code == 409

    client.delete(f"{API}/availability/overrides/{blocked_day.isoformat()}")
    assert _at(blocked_day, 9) in _slot_times(client, event["slug"], blocked_day)


# Booking rules ---------------------------------------------------------------


def test_event_type_rule_validation(client: TestClient) -> None:
    _host(client)
    event = _event(client)
    assert event["buffer_before_minutes"] == 0
    assert event["minimum_notice_minutes"] == 0
    assert event["max_days_in_advance"] == 60
    assert event["daily_booking_limit"] is None

    base = {"title": "Rules call", "duration_minutes": 45, "slot_interval_minutes": 30}
    for invalid in ({"buffer_before_minutes": 241}, {"buffer_after_minutes": -1}, {"daily_booking_limit": 0}, {"max_days_in_advance": 0}, {"minimum_notice_minutes": -5}):
        assert client.post(f"{API}/event-types", json={**base, **invalid}).status_code == 422

    unlimited = _event(client, max_days_in_advance=None, daily_booking_limit=3, buffer_after_minutes=10)
    assert unlimited["max_days_in_advance"] is None
    assert unlimited["daily_booking_limit"] == 3
    assert unlimited["buffer_after_minutes"] == 10


def test_buffers_block_slots_around_existing_bookings(client: TestClient) -> None:
    _host(client)
    event = _event(client, duration_minutes=30, buffer_before_minutes=15, buffer_after_minutes=15)
    day = TODAY + timedelta(days=2)
    assert _book(client, event["slug"], _at(day, 10)).status_code == 201

    slots = _slot_times(client, event["slug"], day)
    # Booking occupies 09:45-10:45 with buffers; candidates need 15 minutes either side.
    assert _at(day, 9) in slots
    assert _at(day, 11) in slots
    for blocked in (_at(day, 9, 30), _at(day, 10), _at(day, 10, 30)):
        assert blocked not in slots

    rejected = _book(client, event["slug"], _at(day, 10, 30))
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "slot_unavailable"
    assert _book(client, event["slug"], _at(day, 11)).status_code == 201


def test_minimum_notice_excludes_near_slots(client: TestClient) -> None:
    _host(client)
    event = _event(client, duration_minutes=30, minimum_notice_minutes=3 * 24 * 60)
    near = TODAY + timedelta(days=1)
    far = TODAY + timedelta(days=5)

    assert _slot_times(client, event["slug"], near) == set()
    assert _at(far, 9) in _slot_times(client, event["slug"], far)
    assert _book(client, event["slug"], _at(near, 9)).status_code == 409
    assert _book(client, event["slug"], _at(far, 9)).status_code == 201


def test_booking_window_caps_slot_range(client: TestClient) -> None:
    _host(client)
    event = _event(client, duration_minutes=30, max_days_in_advance=3)
    last = TODAY + timedelta(days=3)

    slots = _slot_times(client, event["slug"], TODAY + timedelta(days=1), TODAY + timedelta(days=10))
    assert slots
    assert max(slot.date() for slot in slots) == last
    assert _slot_times(client, event["slug"], TODAY + timedelta(days=4)) == set()
    assert _book(client, event["slug"], _at(TODAY + timedelta(days=5), 9)).status_code == 409
    assert _book(client, event["slug"], _at(last, 9)).status_code == 201


def test_daily_limit_counts_only_this_event_type(client: TestClient) -> None:
    _host(client)
    limited = _event(client, duration_minutes=30, daily_booking_limit=1)
    other = _event(client, duration_minutes=60)
    day = TODAY + timedelta(days=2)
    next_day = day + timedelta(days=1)

    # Bookings of a different event type do not consume the limit.
    assert _book(client, other["slug"], _at(day, 14)).status_code == 201
    assert _at(day, 9) in _slot_times(client, limited["slug"], day)

    assert _book(client, limited["slug"], _at(day, 9)).status_code == 201
    assert _slot_times(client, limited["slug"], day) == set()
    assert _at(next_day, 9) in _slot_times(client, limited["slug"], next_day)
    assert _book(client, limited["slug"], _at(day, 11)).status_code == 409
