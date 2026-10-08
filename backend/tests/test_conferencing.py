import uuid
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.events import BOOKING_CANCELLED, BOOKING_CONFIRMED, BOOKING_RESCHEDULED, DomainEvent, event_bus
from app.domains.bookings.models import Booking
from app.domains.calendars.models import BookingCalendarEvent
from app.domains.conferencing.models import BookingMeeting
from tests.integration_fakes import (
    FakeProviders,
    add_calendar_connection,
    add_zoom_connection,
    at,
    book,
    providers_fixture,  # noqa: F401
    session,
    setup_host,
)


GOOGLE = "www.googleapis.com"
ZOOM = "api.zoom.us"


def publish(name: str, booking_id: str, **payload: str) -> None:
    event_bus.publish(DomainEvent(name, {"booking_id": booking_id, **payload}))


def meeting_url(booking_id: str) -> str | None:
    with session() as db:
        booking = db.get(Booking, uuid.UUID(booking_id))
        assert booking is not None
        return booking.meeting_url


# Event type locations -------------------------------------------------------------------


def test_location_values_are_validated_per_type(client: TestClient) -> None:
    setup_host(client)
    base = {"title": "Call", "duration_minutes": 30, "slot_interval_minutes": 30}

    missing = client.post("/api/v1/event-types", json={**base, "location_type": "in_person"})
    bad_link = client.post("/api/v1/event-types", json={**base, "location_type": "custom_link", "location_value": "not a url"})
    bad_phone = client.post("/api/v1/event-types", json={**base, "location_type": "phone", "location_value": "call me"})
    phone = client.post("/api/v1/event-types", json={**base, "location_type": "phone", "location_value": "+91 98765 43210"})
    cleared = client.post("/api/v1/event-types", json={**base, "location_type": "none", "location_value": "ignored"})

    assert missing.status_code == 422
    assert bad_link.status_code == 422
    assert bad_phone.status_code == 422
    assert phone.status_code == 201
    assert phone.json()["location_value"] == "+91 98765 43210"
    assert cleared.json()["location_value"] is None


def test_online_locations_require_connected_integrations(client: TestClient, providers: FakeProviders) -> None:
    event = setup_host(client)
    base = {key: value for key, value in event.items() if key not in {"id", "slug"}}

    meet = client.patch(f"/api/v1/event-types/{event['id']}", json={**base, "location_type": "google_meet"})
    zoom = client.patch(f"/api/v1/event-types/{event['id']}", json={**base, "location_type": "zoom"})
    teams = client.patch(f"/api/v1/event-types/{event['id']}", json={**base, "location_type": "microsoft_teams"})

    assert meet.status_code == 422
    assert meet.json()["code"] == "google_calendar_required"
    assert zoom.status_code == 422
    assert zoom.json()["code"] == "zoom_connection_required"
    assert teams.status_code == 422

    add_calendar_connection()
    add_zoom_connection()
    assert client.patch(f"/api/v1/event-types/{event['id']}", json={**base, "location_type": "google_meet"}).status_code == 200
    assert client.patch(f"/api/v1/event-types/{event['id']}", json={**base, "location_type": "zoom"}).status_code == 200


# Meeting links -------------------------------------------------------------------------


def test_custom_link_sets_meeting_url(client: TestClient, providers: FakeProviders) -> None:
    event = setup_host(client, event={"location_type": "custom_link", "location_value": "https://whereby.com/avery"})

    booking = book(client, event["slug"], 10)

    assert meeting_url(booking["id"]) == "https://whereby.com/avery"


def test_google_meet_creates_a_single_google_event(client: TestClient, providers: FakeProviders) -> None:
    setup_host(client)
    add_calendar_connection()
    event = client.post(
        "/api/v1/event-types",
        json={"title": "Meet call", "duration_minutes": 30, "slot_interval_minutes": 30, "location_type": "google_meet"},
    ).json()

    booking = book(client, event["slug"], 10)
    publish(BOOKING_CONFIRMED, booking["id"])

    creates = [call for call in providers.calls_to(GOOGLE, "POST") if call[2].endswith("/events")]
    assert len(creates) == 1
    assert creates[0][3]["conferenceData"]["createRequest"]["conferenceSolutionKey"] == {"type": "hangoutsMeet"}
    assert meeting_url(booking["id"]) == "https://meet.google.com/abc-defg-hij"
    with session() as db:
        assert len(list(db.scalars(select(BookingCalendarEvent)))) == 1


def test_google_meet_with_outlook_destination_creates_both_events(client: TestClient, providers: FakeProviders) -> None:
    setup_host(client)
    add_calendar_connection("google", destination=False, conflicts=False)
    add_calendar_connection("microsoft", calendar_id="AAMk-default", conflicts=False)
    event = client.post(
        "/api/v1/event-types",
        json={"title": "Meet call", "duration_minutes": 30, "slot_interval_minutes": 30, "location_type": "google_meet"},
    ).json()

    booking = book(client, event["slug"], 10)

    assert meeting_url(booking["id"]) == "https://meet.google.com/abc-defg-hij"
    outlook = [call for call in providers.calls if call[0] == "graph.microsoft.com" and call[1] == "POST"]
    assert len(outlook) == 1
    assert outlook[0][3]["location"] == {"displayName": "https://meet.google.com/abc-defg-hij"}
    # Graph cannot silence invitations, so the invitee is not added as an attendee.
    assert "attendees" not in outlook[0][3]


def test_zoom_meeting_lifecycle(client: TestClient, providers: FakeProviders) -> None:
    setup_host(client)
    add_zoom_connection()
    event = client.post(
        "/api/v1/event-types",
        json={"title": "Zoom call", "duration_minutes": 45, "slot_interval_minutes": 60, "location_type": "zoom"},
    ).json()

    booking = book(client, event["slug"], 10)
    publish(BOOKING_CONFIRMED, booking["id"])

    creates = providers.calls_to(ZOOM, "POST", "/v2/users/me/meetings")
    assert len(creates) == 1
    assert creates[0][3]["type"] == 2
    assert creates[0][3]["duration"] == 45
    assert creates[0][3]["start_time"].endswith("Z")
    url = meeting_url(booking["id"])
    assert url is not None and url.startswith("https://zoom.us/j/")

    with session() as db:
        meeting = db.scalar(select(BookingMeeting))
        assert meeting is not None
        stored = db.get(Booking, uuid.UUID(booking["id"]))
        assert stored is not None
        stored.starts_at = at(13)
        stored.ends_at = at(13, 45)
        db.commit()

    publish(BOOKING_RESCHEDULED, booking["id"])
    patches = providers.calls_to(ZOOM, "PATCH", f"/v2/meetings/{meeting.external_meeting_id}")
    assert len(patches) == 1
    assert patches[0][3]["start_time"] == at(13).strftime("%Y-%m-%dT%H:%M:%SZ")

    publish(BOOKING_CANCELLED, booking["id"])
    assert len(providers.calls_to(ZOOM, "DELETE", f"/v2/meetings/{meeting.external_meeting_id}")) == 1
    with session() as db:
        assert db.scalar(select(BookingMeeting)) is None


def test_zoom_failure_leaves_meeting_url_empty(client: TestClient, providers: FakeProviders) -> None:
    setup_host(client)
    add_zoom_connection()
    event = client.post(
        "/api/v1/event-types",
        json={"title": "Zoom call", "duration_minutes": 30, "slot_interval_minutes": 30, "location_type": "zoom"},
    ).json()
    providers.failures[(ZOOM, "POST", "/v2/users/me/meetings")] = 500

    booking = book(client, event["slug"], 10)

    assert booking["status"] == "confirmed"
    assert meeting_url(booking["id"]) is None


def test_zoom_oauth_connects_and_disconnect_revokes(client: TestClient, providers: FakeProviders) -> None:
    setup_host(client)
    authorize = client.get("/api/v1/conferencing/oauth/zoom/authorize").json()["authorization_url"]
    params = parse_qs(urlparse(authorize).query)
    assert params["redirect_uri"] == ["http://localhost:8000/api/v1/conferencing/oauth/zoom/callback"]

    callback = client.get("/api/v1/conferencing/oauth/zoom/callback", params={"code": "abc", "state": params["state"][0]}, follow_redirects=False)
    assert callback.headers["location"].endswith("/dashboard/integrations?connected=zoom")
    token_call = providers.calls_to("zoom.us", "POST", "/oauth/token")[0]
    assert token_call[3]["grant_type"] == "authorization_code"

    # A calendar state cannot complete the Zoom flow.
    from app.core.oauth import create_oauth_state
    from tests.integration_fakes import host_id

    wrong = create_oauth_state(host_id(), kind="calendar", provider="zoom")
    rejected = client.get("/api/v1/conferencing/oauth/zoom/callback", params={"code": "abc", "state": wrong}, follow_redirects=False)
    assert rejected.headers["location"].endswith("error=invalid_state")

    connections = client.get("/api/v1/conferencing/connections").json()
    assert connections[0]["account_email"] == "host@zoom.example"
    assert client.delete(f"/api/v1/conferencing/connections/{connections[0]['id']}").status_code == 204
    assert providers.calls_to("zoom.us", "POST", "/oauth/revoke")
    assert client.get("/api/v1/conferencing/connections").json() == []


def test_public_pages_hide_custom_meeting_link(client: TestClient, providers: FakeProviders) -> None:
    event = setup_host(client, event={"location_type": "custom_link", "location_value": "https://whereby.com/avery"})

    page = client.get(f"/api/v1/public/avery/{event['slug']}").json()
    profile = client.get("/api/v1/public/avery").json()

    assert page["event_type"]["location_type"] == "custom_link"
    assert page["event_type"]["location_value"] is None
    assert all(item["location_value"] is None for item in profile["event_types"])
