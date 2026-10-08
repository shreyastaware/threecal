"""Google Calendar provider.

API references (verified against developers.google.com):
- OAuth web server flow: https://accounts.google.com/o/oauth2/v2/auth, token https://oauth2.googleapis.com/token,
  revoke https://oauth2.googleapis.com/revoke; ``access_type=offline`` + ``prompt=consent`` return a refresh token,
  a revoked/expired refresh token returns ``invalid_grant``.
- GET  /calendar/v3/users/me/calendarList                       calendars (id, summary, primary, accessRole)
- POST /calendar/v3/freeBusy                                     busy intervals per calendar
- POST /calendar/v3/calendars/{id}/events?conferenceDataVersion=1&sendUpdates=none
       conferenceData.createRequest (hangoutsMeet) -> hangoutLink / entryPoints[video].uri
- PATCH/DELETE /calendar/v3/calendars/{id}/events/{eventId}?sendUpdates=none
"""

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlencode

from app.core.config import settings
from app.core.oauth import OAuthTokens, ProviderError
from app.domains.calendars.models import CalendarProviderName
from app.domains.calendars.providers.base import (
    BusyInterval,
    CalendarEventInput,
    CalendarEventResult,
    CalendarProvider,
    ProviderCalendar,
)


AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
API_URL = "https://www.googleapis.com/calendar/v3"
SCOPES = (
    "openid",
    "email",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.freebusy",
    "https://www.googleapis.com/auth/calendar.events",
)
_WRITE_ROLES = {"owner", "writer"}


def _rfc3339(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class GoogleCalendarProvider(CalendarProvider):
    name = CalendarProviderName.GOOGLE
    conference = "google_meet"

    def is_configured(self) -> bool:
        return bool(settings.google_client_id and settings.google_client_secret)

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            # Always show consent so Google issues a refresh token on reconnect too.
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code(self, *, code: str, redirect_uri: str) -> OAuthTokens:
        return self._token_request(
            TOKEN_URL,
            {
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    def refresh(self, refresh_token: str) -> OAuthTokens:
        return self._token_request(
            TOKEN_URL,
            {
                "refresh_token": refresh_token,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
            },
            previous_refresh_token=refresh_token,
        )

    def revoke(self, tokens: OAuthTokens) -> None:
        # Revoking the refresh token also invalidates its access tokens.
        token = tokens.refresh_token or tokens.access_token
        self._send("POST", REVOKE_URL, data={"token": token})

    def account_email(self, access_token: str) -> str:
        body = self._request_json("GET", USERINFO_URL, access_token=access_token)
        email = body.get("email")
        if not isinstance(email, str) or not email:
            raise ProviderError("Google did not return the account email.")
        return email.lower()

    def list_calendars(self, access_token: str) -> list[ProviderCalendar]:
        calendars: list[ProviderCalendar] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"maxResults": 250}
            if page_token:
                params["pageToken"] = page_token
            body = self._request_json("GET", f"{API_URL}/users/me/calendarList", access_token=access_token, params=params)
            for item in body.get("items", []):
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                calendars.append(
                    ProviderCalendar(
                        id=str(item["id"]),
                        name=str(item.get("summaryOverride") or item.get("summary") or item["id"]),
                        is_primary=bool(item.get("primary")),
                        can_write=item.get("accessRole") in _WRITE_ROLES,
                    )
                )
            page_token = body.get("nextPageToken")
            if not page_token:
                return calendars

    def busy_intervals(self, access_token: str, calendar_ids: list[str], start: datetime, end: datetime) -> list[BusyInterval]:
        if not calendar_ids:
            return []
        body = self._request_json(
            "POST",
            f"{API_URL}/freeBusy",
            access_token=access_token,
            json={
                "timeMin": _rfc3339(start),
                "timeMax": _rfc3339(end),
                "items": [{"id": calendar_id} for calendar_id in calendar_ids],
            },
        )
        intervals: list[BusyInterval] = []
        for calendar_id, calendar in (body.get("calendars") or {}).items():
            if not isinstance(calendar, dict):
                continue
            if calendar.get("errors"):
                raise ProviderError(f"Google could not read free/busy for calendar {calendar_id}.")
            for busy in calendar.get("busy", []):
                intervals.append(BusyInterval(start=_parse(busy["start"]), end=_parse(busy["end"])))
        return intervals

    def create_event(self, access_token: str, calendar_id: str, event: CalendarEventInput) -> CalendarEventResult:
        payload = self._event_payload(event)
        params: dict[str, Any] = {"sendUpdates": "none"}
        if event.conference == "google_meet":
            params["conferenceDataVersion"] = 1
            payload["conferenceData"] = {
                "createRequest": {
                    # Stable per booking so a retried request does not create a second Meet.
                    "requestId": f"threecal-{event.booking_id}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }
        body = self._request_json(
            "POST",
            f"{API_URL}/calendars/{quote(calendar_id, safe='')}/events",
            access_token=access_token,
            params=params,
            json=payload,
        )
        event_id = body.get("id")
        if not isinstance(event_id, str):
            raise ProviderError("Google did not return the created event id.")
        return CalendarEventResult(external_event_id=event_id, meeting_url=self._meet_link(body))

    def update_event(self, access_token: str, calendar_id: str, event_id: str, event: CalendarEventInput) -> None:
        self._request_json(
            "PATCH",
            f"{API_URL}/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}",
            access_token=access_token,
            # conferenceDataVersion=1 keeps an attached Meet conference on modification.
            params={"sendUpdates": "none", "conferenceDataVersion": 1},
            json={"start": {"dateTime": _rfc3339(event.starts_at)}, "end": {"dateTime": _rfc3339(event.ends_at)}, "description": event.description, "location": event.location},
        )

    def delete_event(self, access_token: str, calendar_id: str, event_id: str) -> None:
        response = self._send(
            "DELETE",
            f"{API_URL}/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}",
            access_token=access_token,
            params={"sendUpdates": "none"},
        )
        if response.status_code >= 400 and response.status_code not in (404, 410):
            raise self._error(response)

    @staticmethod
    def _event_payload(event: CalendarEventInput) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "summary": event.title,
            "description": event.description,
            "start": {"dateTime": _rfc3339(event.starts_at)},
            "end": {"dateTime": _rfc3339(event.ends_at)},
            # Threecal emails the invitee itself; sendUpdates=none keeps Google quiet.
            "attendees": [{"email": event.attendee_email, "displayName": event.attendee_name}],
            "extendedProperties": {"private": {"threecalBookingId": event.booking_id}},
            "reminders": {"useDefault": True},
        }
        if event.location:
            payload["location"] = event.location
        return payload

    @staticmethod
    def _meet_link(body: dict[str, Any]) -> str | None:
        conference = body.get("conferenceData") or {}
        for entry in conference.get("entryPoints", []) if isinstance(conference, dict) else []:
            if isinstance(entry, dict) and entry.get("entryPointType") == "video" and entry.get("uri"):
                return str(entry["uri"])
        link = body.get("hangoutLink")
        return str(link) if link else None
