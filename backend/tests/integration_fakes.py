"""In-memory Google, Microsoft Graph and Zoom APIs for integration tests (httpx MockTransport)."""

import json
import uuid
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core import database
from app.core.config import settings
from app.core.database import get_db
from app.core.encryption import encrypt_secret
from app.core.oauth import OAuthHTTPClient
from app.domains.calendars import busy_cache
from app.domains.calendars.models import CalendarConnection, SelectedCalendar
from app.domains.conferencing.models import ConferencingConnection
from app.domains.users.models import User
from app.main import app


@dataclass
class FakeProviders:
    google_busy: list[tuple[str, str]] = field(default_factory=list)
    graph_busy: list[dict[str, Any]] = field(default_factory=list)
    # (host, method, path prefix) -> status code to return.
    failures: dict[tuple[str, str, str], int] = field(default_factory=dict)
    timeout_hosts: set[str] = field(default_factory=set)
    revoked_refresh_tokens: set[str] = field(default_factory=set)
    calls: list[tuple[str, str, str, Any]] = field(default_factory=list)
    counter: int = 0

    def calls_to(self, host: str, method: str, path_prefix: str = "") -> list[tuple[str, str, str, Any]]:
        return [call for call in self.calls if call[0] == host and call[1] == method and call[2].startswith(path_prefix)]

    def handler(self, request: httpx.Request) -> httpx.Response:
        host, method, path = request.url.host, request.method, request.url.path
        body: Any = None
        if request.content:
            content_type = request.headers.get("content-type", "")
            if "json" in content_type:
                body = json.loads(request.content)
            else:
                body = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        self.calls.append((host, method, path, body))
        if host in self.timeout_hosts:
            raise httpx.ConnectTimeout("timed out", request=request)
        for (fail_host, fail_method, prefix), status_code in self.failures.items():
            if fail_host == host and fail_method == method and path.startswith(prefix):
                return httpx.Response(status_code, json={"error": {"code": status_code, "message": "boom"}})
        self.counter += 1
        if path.endswith("/token"):
            return self._token(body or {})
        if host == "openidconnect.googleapis.com":
            return httpx.Response(200, json={"email": "Host@Gmail.com"})
        if host == "www.googleapis.com":
            return self._google(method, path, body, request)
        if host == "graph.microsoft.com":
            return self._graph(method, path, body)
        if host == "api.zoom.us":
            return self._zoom(method, path, body)
        if path.endswith("/revoke"):
            return httpx.Response(200, json={"status": "success"})
        return httpx.Response(404, json={"error": "not_found"})

    def _token(self, body: dict[str, str]) -> httpx.Response:
        if body.get("grant_type") == "refresh_token" and body.get("refresh_token") in self.revoked_refresh_tokens:
            return httpx.Response(400, json={"error": "invalid_grant", "error_description": "Token has been revoked."})
        return httpx.Response(
            200,
            json={"access_token": f"access-{self.counter}", "refresh_token": f"refresh-{self.counter}", "expires_in": 3600, "token_type": "Bearer"},
        )

    def _google(self, method: str, path: str, body: Any, request: httpx.Request) -> httpx.Response:
        if path.endswith("/users/me/calendarList"):
            return httpx.Response(
                200,
                json={"items": [
                    {"id": "host@gmail.com", "summary": "Host", "primary": True, "accessRole": "owner"},
                    {"id": "team@group.calendar.google.com", "summary": "Team", "accessRole": "reader"},
                ]},
            )
        if path.endswith("/freeBusy"):
            calendars = {item["id"]: {"busy": [{"start": start, "end": end} for start, end in self.google_busy]} for item in body["items"]}
            return httpx.Response(200, json={"calendars": calendars})
        if method == "POST" and path.endswith("/events"):
            event: dict[str, Any] = {"id": f"gevt-{self.counter}"}
            if body.get("conferenceData") and request.url.params.get("conferenceDataVersion") == "1":
                event["hangoutLink"] = "https://meet.google.com/abc-defg-hij"
                event["conferenceData"] = {"entryPoints": [{"entryPointType": "video", "uri": "https://meet.google.com/abc-defg-hij"}]}
            return httpx.Response(200, json=event)
        if method == "PATCH":
            return httpx.Response(200, json={"id": path.rsplit("/", 1)[-1]})
        if method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(404)

    def _graph(self, method: str, path: str, body: Any) -> httpx.Response:
        if path == "/v1.0/me":
            return httpx.Response(200, json={"mail": None, "userPrincipalName": "host@outlook.com"})
        if path == "/v1.0/me/calendars":
            return httpx.Response(200, json={"value": [{"id": "AAMk-default", "name": "Calendar", "isDefaultCalendar": True, "canEdit": True}]})
        if path.endswith("/calendarView"):
            return httpx.Response(200, json={"value": self.graph_busy})
        if method == "POST" and path.endswith("/events"):
            event: dict[str, Any] = {"id": f"mevt-{self.counter}"}
            if body.get("isOnlineMeeting"):
                event["onlineMeeting"] = {"joinUrl": "https://teams.microsoft.com/l/meetup-join/abc"}
            return httpx.Response(201, json=event)
        if method == "PATCH":
            return httpx.Response(200, json={})
        if method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(404)

    def _zoom(self, method: str, path: str, body: Any) -> httpx.Response:
        if path == "/v2/users/me":
            return httpx.Response(200, json={"email": "host@zoom.example"})
        if method == "POST" and path == "/v2/users/me/meetings":
            return httpx.Response(201, json={"id": 85746065432 + self.counter, "join_url": f"https://zoom.us/j/{self.counter}"})
        if method in {"PATCH", "DELETE"}:
            return httpx.Response(204)
        return httpx.Response(404)


@pytest.fixture(name="providers")
def providers_fixture(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> Generator[FakeProviders, None, None]:
    fake = FakeProviders()
    for name in ("google_client_id", "google_client_secret", "microsoft_client_id", "microsoft_client_secret", "zoom_client_id", "zoom_client_secret"):
        monkeypatch.setattr(settings, name, f"test-{name}")
    monkeypatch.setattr(OAuthHTTPClient, "transport", httpx.MockTransport(fake.handler))
    # Event handlers open their own sessions; point them at the test database.
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    bind = db.get_bind()
    generator.close()
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=bind, autoflush=False, expire_on_commit=False))
    busy_cache.clear()
    yield fake
    busy_cache.clear()


def session() -> Session:
    return database.SessionLocal()


def setup_host(client: TestClient, *, event: dict[str, Any] | None = None) -> dict[str, Any]:
    """Register a UTC host with 09:00-17:00 availability tomorrow and a free 30 minute event type."""
    client.post("/api/v1/auth/register", json={"full_name": "Avery Stone", "email": "avery@example.com", "password": "strong-password"})
    client.patch("/api/v1/users/me", json={"username": "avery", "timezone": "UTC"})
    weekday = tomorrow().weekday()
    client.put("/api/v1/availability", json={"working_hours": [{"weekday": weekday, "start_time": "09:00", "end_time": "17:00", "is_enabled": True, "breaks": []}]})
    response = client.post(
        "/api/v1/event-types",
        json={"title": "Strategy call", "duration_minutes": 30, "slot_interval_minutes": 30, "max_days_in_advance": 30, **(event or {})},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def tomorrow() -> date:
    return date.today() + timedelta(days=1)


def at(hour: int, minute: int = 0) -> datetime:
    return datetime.combine(tomorrow(), datetime.min.time(), timezone.utc).replace(hour=hour, minute=minute)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def host_id() -> uuid.UUID:
    with session() as db:
        user = db.query(User).filter(User.email == "avery@example.com").one()
        return user.id


def add_calendar_connection(
    provider: str = "google",
    *,
    calendar_id: str = "host@gmail.com",
    conflicts: bool = True,
    destination: bool = True,
    expires_in: timedelta = timedelta(hours=1),
    refresh_token: str = "refresh-initial",
) -> uuid.UUID:
    with session() as db:
        user_id = host_id()
        connection = CalendarConnection(
            user_id=user_id,
            provider=provider,
            account_email=f"host@{provider}.example",
            encrypted_access_token=encrypt_secret("access-initial"),
            encrypted_refresh_token=encrypt_secret(refresh_token),
            token_expires_at=datetime.now(timezone.utc) + expires_in,
        )
        db.add(connection)
        db.flush()
        db.add(
            SelectedCalendar(
                connection_id=connection.id,
                user_id=user_id,
                external_calendar_id=calendar_id,
                name="Primary",
                check_conflicts=conflicts,
                is_destination=destination,
            )
        )
        db.commit()
        return connection.id


def add_zoom_connection() -> uuid.UUID:
    with session() as db:
        connection = ConferencingConnection(
            user_id=host_id(),
            provider="zoom",
            account_email="host@zoom.example",
            encrypted_access_token=encrypt_secret("zoom-access"),
            encrypted_refresh_token=encrypt_secret("zoom-refresh"),
            token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(connection)
        db.commit()
        return connection.id


def slots(client: TestClient, event_slug: str) -> list[str]:
    day = tomorrow().isoformat()
    response = client.get(f"/api/v1/public/avery/{event_slug}/slots", params={"start": day, "end": day, "timezone": "UTC"})
    assert response.status_code == 200, response.text
    return [datetime.fromisoformat(item["starts_at"].replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%H:%M") for item in response.json()]


def book(client: TestClient, event_slug: str, hour: int, minute: int = 0) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/public/avery/{event_slug}/bookings",
        json={
            "invitee_name": "Jordan Lee",
            "invitee_email": "jordan@example.com",
            "invitee_timezone": "UTC",
            "notes": "Discuss Q3 plan",
            "starts_at": iso(at(hour, minute)),
        },
    )
    assert response.status_code == 201, response.text
    return dict(response.json())
