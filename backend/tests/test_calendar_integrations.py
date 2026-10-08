import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.events import BOOKING_CANCELLED, BOOKING_CONFIRMED, BOOKING_RESCHEDULED, DomainEvent, event_bus
from app.core.oauth import OAuthStateError, create_oauth_state, verify_oauth_state
from app.domains.bookings.models import Booking
from app.domains.calendars.models import BookingCalendarEvent, CalendarConnection, SelectedCalendar
from app.domains.conferencing.models import BookingMeeting, ConferencingConnection
from tests.integration_fakes import (
    FakeProviders,
    add_calendar_connection,
    add_zoom_connection,
    at,
    book,
    iso,
    providers_fixture,  # noqa: F401
    session,
    setup_host,
    slots,
)


GOOGLE = "www.googleapis.com"
GRAPH = "graph.microsoft.com"


def publish(name: str, booking_id: str, **payload: str) -> None:
    event_bus.publish(DomainEvent(name, {"booking_id": booking_id, **payload}))


# OAuth -------------------------------------------------------------------------


def test_oauth_state_is_bound_to_user_kind_and_provider() -> None:
    user_id = uuid.uuid4()
    state = create_oauth_state(user_id, kind="calendar", provider="google")

    assert verify_oauth_state(state, kind="calendar", provider="google") == user_id
    for kind, provider in (("calendar", "microsoft"), ("conferencing", "google")):
        with pytest.raises(OAuthStateError):
            verify_oauth_state(state, kind=kind, provider=provider)
    with pytest.raises(OAuthStateError):
        verify_oauth_state(state + "x", kind="calendar", provider="google")
    with pytest.raises(OAuthStateError):
        verify_oauth_state(None, kind="calendar", provider="google")


def test_endpoints_return_503_when_provider_not_configured(client: TestClient) -> None:
    setup_host(client)
    response = client.get("/api/v1/calendars/oauth/google/authorize")
    zoom = client.get("/api/v1/conferencing/oauth/zoom/authorize")

    assert response.status_code == 503
    assert response.json()["code"] == "not_configured"
    assert zoom.status_code == 503
    assert client.get("/api/v1/calendars/oauth/unknown/authorize").status_code == 404


def test_google_oauth_flow_connects_and_selects_primary_calendar(client: TestClient, providers: FakeProviders) -> None:
    setup_host(client)
    authorize = client.get("/api/v1/calendars/oauth/google/authorize")
    assert authorize.status_code == 200
    url = urlparse(authorize.json()["authorization_url"])
    params = parse_qs(url.query)
    assert url.netloc == "accounts.google.com"
    assert params["access_type"] == ["offline"]
    assert params["redirect_uri"] == ["http://localhost:8000/api/v1/calendars/oauth/google/callback"]
    assert "https://www.googleapis.com/auth/calendar.events" in params["scope"][0]

    tampered = client.get("/api/v1/calendars/oauth/google/callback", params={"code": "c", "state": "bad"}, follow_redirects=False)
    assert tampered.status_code == 302
    assert tampered.headers["location"].endswith("/dashboard/integrations?error=invalid_state")

    denied = client.get("/api/v1/calendars/oauth/google/callback", params={"error": "access_denied", "state": params["state"][0]}, follow_redirects=False)
    assert denied.headers["location"].endswith("?error=access_denied")

    callback = client.get("/api/v1/calendars/oauth/google/callback", params={"code": "auth-code", "state": params["state"][0]}, follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "http://localhost:3000/dashboard/integrations?connected=google"

    connections = client.get("/api/v1/calendars/connections").json()
    assert len(connections) == 1
    assert connections[0]["account_email"] == "host@gmail.com"
    assert connections[0]["status"] == "active"
    assert connections[0]["conflict_calendar_ids"] == ["host@gmail.com"]
    assert connections[0]["destination_calendar_id"] == "host@gmail.com"
    with session() as db:
        stored = db.scalar(select(CalendarConnection))
        assert stored is not None
        # Tokens are encrypted at rest.
        assert "access-" not in stored.encrypted_access_token


def test_update_connection_validates_calendars(client: TestClient, providers: FakeProviders) -> None:
    setup_host(client)
    connection_id = add_calendar_connection()

    calendars = client.get(f"/api/v1/calendars/connections/{connection_id}/calendars").json()
    assert {item["id"] for item in calendars} == {"host@gmail.com", "team@group.calendar.google.com"}

    read_only = client.patch(
        f"/api/v1/calendars/connections/{connection_id}",
        json={"conflict_calendar_ids": [], "destination_calendar_id": "team@group.calendar.google.com"},
    )
    assert read_only.status_code == 422
    unknown = client.patch(f"/api/v1/calendars/connections/{connection_id}", json={"conflict_calendar_ids": ["nope"]})
    assert unknown.status_code == 422

    updated = client.patch(
        f"/api/v1/calendars/connections/{connection_id}",
        json={"conflict_calendar_ids": ["host@gmail.com", "team@group.calendar.google.com"], "destination_calendar_id": "host@gmail.com"},
    )
    assert updated.status_code == 200
    assert set(updated.json()["conflict_calendar_ids"]) == {"host@gmail.com", "team@group.calendar.google.com"}


def test_disconnect_revokes_and_deletes(client: TestClient, providers: FakeProviders) -> None:
    setup_host(client)
    connection_id = add_calendar_connection()

    response = client.delete(f"/api/v1/calendars/connections/{connection_id}")

    assert response.status_code == 204
    assert providers.calls_to("oauth2.googleapis.com", "POST", "/revoke")
    assert client.get("/api/v1/calendars/connections").json() == []
    with session() as db:
        assert db.scalar(select(SelectedCalendar)) is None


# Tokens -------------------------------------------------------------------------


def test_expired_access_token_is_refreshed(client: TestClient, providers: FakeProviders) -> None:
    event = setup_host(client)
    connection_id = add_calendar_connection(expires_in=timedelta(seconds=-10))

    slots(client, event["slug"])

    assert providers.calls_to("oauth2.googleapis.com", "POST", "/token")
    with session() as db:
        connection = db.get(CalendarConnection, connection_id)
        assert connection is not None
        assert connection.token_expires_at is not None
        expires_at = connection.token_expires_at.replace(tzinfo=timezone.utc)
        assert expires_at > datetime.now(timezone.utc)
        assert connection.status == "active"


def test_invalid_grant_marks_connection_for_reconnection_and_fails_open(client: TestClient, providers: FakeProviders) -> None:
    event = setup_host(client)
    providers.revoked_refresh_tokens.add("refresh-initial")
    providers.google_busy = [(iso(at(9)), iso(at(12)))]
    add_calendar_connection(expires_in=timedelta(seconds=-10))

    available = slots(client, event["slug"])

    assert "09:00" in available
    connections = client.get("/api/v1/calendars/connections").json()
    assert connections[0]["status"] == "reconnect_required"
    listing = client.get(f"/api/v1/calendars/connections/{connections[0]['id']}/calendars")
    assert listing.status_code == 409
    assert listing.json()["code"] == "reconnect_required"


# Busy times -------------------------------------------------------------------------


def test_busy_times_from_conflict_calendars_hide_slots_with_buffers(client: TestClient, providers: FakeProviders) -> None:
    event = setup_host(client, event={"buffer_after_minutes": 15})
    providers.google_busy = [(iso(at(10)), iso(at(10, 30)))]
    add_calendar_connection()

    available = slots(client, event["slug"])

    assert "10:00" not in available
    # The 15 minute buffer also blocks the slot right before and after the busy time.
    assert "09:30" not in available
    assert "10:30" not in available
    assert "11:00" in available
    assert "09:00" in available


def test_busy_times_are_cached(client: TestClient, providers: FakeProviders) -> None:
    event = setup_host(client)
    add_calendar_connection()

    slots(client, event["slug"])
    slots(client, event["slug"])

    assert len(providers.calls_to(GOOGLE, "POST", "/calendar/v3/freeBusy")) == 1


def test_non_conflict_calendars_are_ignored(client: TestClient, providers: FakeProviders) -> None:
    event = setup_host(client)
    providers.google_busy = [(iso(at(10)), iso(at(10, 30)))]
    add_calendar_connection(conflicts=False)

    assert "10:00" in slots(client, event["slug"])
    assert not providers.calls_to(GOOGLE, "POST", "/calendar/v3/freeBusy")


@pytest.mark.parametrize("failure", ["error", "timeout"])
def test_provider_outage_fails_open(client: TestClient, providers: FakeProviders, failure: str) -> None:
    event = setup_host(client)
    providers.google_busy = [(iso(at(10)), iso(at(10, 30)))]
    if failure == "error":
        providers.failures[(GOOGLE, "POST", "/calendar/v3/freeBusy")] = 503
    else:
        providers.timeout_hosts.add(GOOGLE)
    add_calendar_connection()

    assert "10:00" in slots(client, event["slug"])
    booking = book(client, event["slug"], 10)
    assert booking["status"] == "confirmed"


def test_outlook_busy_times_use_calendar_view_and_skip_free_and_own_events(client: TestClient, providers: FakeProviders) -> None:
    event = setup_host(client)
    add_calendar_connection("microsoft", calendar_id="AAMk-default")
    booking = book(client, event["slug"], 14)
    with session() as db:
        own = db.scalar(select(BookingCalendarEvent).where(BookingCalendarEvent.booking_id == uuid.UUID(booking["id"])))
        assert own is not None
        own_id = own.external_event_id
    providers.graph_busy = [
        {"id": "busy-1", "showAs": "busy", "isCancelled": False, "start": {"dateTime": at(11).replace(tzinfo=None).isoformat() + ".0000000"}, "end": {"dateTime": at(11, 30).replace(tzinfo=None).isoformat() + ".0000000"}},
        {"id": "free-1", "showAs": "free", "isCancelled": False, "start": {"dateTime": at(12).replace(tzinfo=None).isoformat()}, "end": {"dateTime": at(12, 30).replace(tzinfo=None).isoformat()}},
        {"id": own_id, "showAs": "busy", "isCancelled": False, "start": {"dateTime": at(14).replace(tzinfo=None).isoformat()}, "end": {"dateTime": at(14, 30).replace(tzinfo=None).isoformat()}},
    ]
    from app.domains.calendars import busy_cache

    busy_cache.clear()

    available = slots(client, event["slug"])

    assert "11:00" not in available
    assert "12:00" in available
    assert "14:00" not in available  # still blocked by the booking itself
    assert providers.calls_to(GRAPH, "GET", "/v1.0/me/calendars/AAMk-default/calendarView")


# Writing bookings -------------------------------------------------------------------


def test_confirmed_booking_is_written_once_then_updated_and_deleted(client: TestClient, providers: FakeProviders) -> None:
    event = setup_host(client, event={"location_type": "in_person", "location_value": "12 Market Street"})
    add_calendar_connection()

    booking = book(client, event["slug"], 10)
    # Re-delivered events must not create a second calendar event.
    publish(BOOKING_CONFIRMED, booking["id"])

    creates = [call for call in providers.calls_to(GOOGLE, "POST") if call[2].endswith("/events")]
    assert len(creates) == 1
    assert "host@gmail.com" in creates[0][2]
    payload = creates[0][3]
    assert payload["summary"] == "Strategy call with Jordan Lee"
    assert payload["attendees"] == [{"email": "jordan@example.com", "displayName": "Jordan Lee"}]
    assert payload["location"] == "12 Market Street"
    assert "Discuss Q3 plan" in payload["description"]
    assert "conferenceData" not in payload
    with session() as db:
        records = list(db.scalars(select(BookingCalendarEvent)))
        assert len(records) == 1

        stored = db.get(Booking, uuid.UUID(booking["id"]))
        assert stored is not None
        previous = stored.starts_at
        stored.starts_at = at(15)
        stored.ends_at = at(15, 30)
        db.commit()

    publish(BOOKING_RESCHEDULED, booking["id"], previous_starts_at=previous.isoformat(), previous_ends_at=previous.isoformat())
    patches = [call for call in providers.calls_to(GOOGLE, "PATCH") if call[2].endswith(records[0].external_event_id)]
    assert len(patches) == 1
    assert patches[0][3]["start"] == {"dateTime": iso(at(15))}

    publish(BOOKING_CANCELLED, booking["id"], cancelled_by="host", reason="")
    assert len(providers.calls_to(GOOGLE, "DELETE")) == 1
    with session() as db:
        assert db.scalar(select(BookingCalendarEvent)) is None


def test_no_destination_means_no_calendar_write(client: TestClient, providers: FakeProviders) -> None:
    event = setup_host(client)
    add_calendar_connection(destination=False)

    book(client, event["slug"], 10)

    assert not [call for call in providers.calls_to(GOOGLE, "POST") if call[2].endswith("/events")]


def test_calendar_write_failure_keeps_booking_confirmed(client: TestClient, providers: FakeProviders) -> None:
    event = setup_host(client)
    add_calendar_connection(conflicts=False)
    providers.failures[(GOOGLE, "POST", "/calendar/v3/calendars/")] = 500

    booking = book(client, event["slug"], 10)

    assert booking["status"] == "confirmed"
    with session() as db:
        assert db.scalar(select(BookingCalendarEvent)) is None


# Account deletion ------------------------------------------------------------------------


def test_account_deletion_removes_integration_rows(client: TestClient, providers: FakeProviders) -> None:
    event = setup_host(client)
    add_calendar_connection()
    add_zoom_connection()
    booking = book(client, event["slug"], 10)
    with session() as db:
        stored = db.get(Booking, uuid.UUID(booking["id"]))
        assert stored is not None
        # Past booking so deletion is not blocked by upcoming bookings.
        stored.starts_at = datetime.now(timezone.utc) - timedelta(days=2)
        stored.ends_at = stored.starts_at + timedelta(minutes=30)
        db.commit()

    response = client.request("DELETE", "/api/v1/users/me", json={"password": "strong-password"})

    assert response.status_code == 204, response.text
    with session() as db:
        for model in (CalendarConnection, SelectedCalendar, BookingCalendarEvent, ConferencingConnection, BookingMeeting):
            assert db.scalar(select(model)) is None, model.__name__
    # Provider tokens are revoked before the rows disappear.
    assert providers.calls_to("oauth2.googleapis.com", "POST", "/revoke")
