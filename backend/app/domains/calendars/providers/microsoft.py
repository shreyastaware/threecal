"""Microsoft Outlook calendar provider (Microsoft identity platform v2.0 + Graph v1.0).

API references (verified against learn.microsoft.com):
- Authorize/token: https://login.microsoftonline.com/{tenant}/oauth2/v2.0/{authorize,token}; ``offline_access``
  returns a (rotating) refresh token; a revoked/expired refresh token returns ``invalid_grant``.
  There is no delegated token revocation endpoint, so disconnecting only deletes stored tokens.
- GET  /me                                       account email (mail, falling back to userPrincipalName)
- GET  /me/calendars                             calendars (id, name, isDefaultCalendar, canEdit)
- GET  /me/calendars/{id}/calendarView           events in a range (showAs, isCancelled); works for
                                                 personal accounts, unlike getSchedule
- POST /me/calendars/{id}/events                 create (isOnlineMeeting + teamsForBusiness -> onlineMeeting.joinUrl)
- PATCH/DELETE /me/events/{id}

Graph cannot suppress invitation emails, so events are created without attendees
(the invitee's details go in the body) because Threecal sends its own emails.
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


GRAPH_URL = "https://graph.microsoft.com/v1.0"
SCOPES = ("openid", "email", "offline_access", "User.Read", "Calendars.ReadWrite")
_FREE_STATES = {"free", "workingElsewhere"}
# Safety bound on calendarView paging per calendar.
_MAX_PAGES = 10


def _graph_datetime(value: datetime) -> dict[str, str]:
    return {"dateTime": value.astimezone(timezone.utc).replace(tzinfo=None).isoformat(), "timeZone": "UTC"}


def _parse_graph_datetime(value: dict[str, Any]) -> datetime:
    # Requested with Prefer: outlook.timezone="UTC", so values are naive UTC with 7 fractional digits.
    raw = str(value["dateTime"])
    if "." in raw:
        head, fraction = raw.split(".", 1)
        raw = f"{head}.{fraction[:6]}"
    parsed = datetime.fromisoformat(raw)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


class MicrosoftCalendarProvider(CalendarProvider):
    name = CalendarProviderName.MICROSOFT
    conference = "microsoft_teams"

    @property
    def _authority(self) -> str:
        return f"https://login.microsoftonline.com/{settings.microsoft_tenant or 'common'}/oauth2/v2.0"

    def is_configured(self) -> bool:
        return bool(settings.microsoft_client_id and settings.microsoft_client_secret)

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": settings.microsoft_client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "response_mode": "query",
            "scope": " ".join(SCOPES),
            "prompt": "select_account",
            "state": state,
        }
        return f"{self._authority}/authorize?{urlencode(params)}"

    def exchange_code(self, *, code: str, redirect_uri: str) -> OAuthTokens:
        return self._token_request(
            f"{self._authority}/token",
            {
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "scope": " ".join(SCOPES),
            },
        )

    def refresh(self, refresh_token: str) -> OAuthTokens:
        return self._token_request(
            f"{self._authority}/token",
            {
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": " ".join(SCOPES),
            },
            previous_refresh_token=refresh_token,
        )

    def revoke(self, tokens: OAuthTokens) -> None:
        # Microsoft has no delegated token revocation endpoint; the stored tokens are deleted instead.
        return None

    def account_email(self, access_token: str) -> str:
        body = self._request_json("GET", f"{GRAPH_URL}/me", access_token=access_token, params={"$select": "mail,userPrincipalName"})
        email = body.get("mail") or body.get("userPrincipalName")
        if not isinstance(email, str) or not email:
            raise ProviderError("Microsoft did not return the account email.")
        return email.lower()

    def list_calendars(self, access_token: str) -> list[ProviderCalendar]:
        calendars: list[ProviderCalendar] = []
        url: str | None = f"{GRAPH_URL}/me/calendars?{urlencode({'$select': 'id,name,isDefaultCalendar,canEdit', '$top': '100'})}"
        while url:
            body = self._request_json("GET", url, access_token=access_token)
            for item in body.get("value", []):
                if isinstance(item, dict) and item.get("id"):
                    calendars.append(
                        ProviderCalendar(
                            id=str(item["id"]),
                            name=str(item.get("name") or "Calendar"),
                            is_primary=bool(item.get("isDefaultCalendar")),
                            can_write=bool(item.get("canEdit")),
                        )
                    )
            next_link = body.get("@odata.nextLink")
            url = str(next_link) if next_link else None
        return calendars

    def busy_intervals(self, access_token: str, calendar_ids: list[str], start: datetime, end: datetime) -> list[BusyInterval]:
        intervals: list[BusyInterval] = []
        for calendar_id in calendar_ids:
            query = urlencode(
                {
                    "startDateTime": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "endDateTime": end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "$select": "id,showAs,isCancelled,start,end",
                    "$top": "500",
                }
            )
            url: str | None = f"{GRAPH_URL}/me/calendars/{quote(calendar_id, safe='')}/calendarView?{query}"
            pages = 0
            while url and pages < _MAX_PAGES:
                body = self._request_json("GET", url, access_token=access_token, headers={"Prefer": 'outlook.timezone="UTC"'})
                for item in body.get("value", []):
                    if not isinstance(item, dict) or item.get("isCancelled") or item.get("showAs") in _FREE_STATES:
                        continue
                    intervals.append(
                        BusyInterval(
                            start=_parse_graph_datetime(item["start"]),
                            end=_parse_graph_datetime(item["end"]),
                            external_event_id=str(item.get("id")) if item.get("id") else None,
                        )
                    )
                next_link = body.get("@odata.nextLink")
                url = str(next_link) if next_link else None
                pages += 1
        return intervals

    def create_event(self, access_token: str, calendar_id: str, event: CalendarEventInput) -> CalendarEventResult:
        payload: dict[str, Any] = {
            "subject": event.title,
            "body": {"contentType": "text", "content": event.description},
            "start": _graph_datetime(event.starts_at),
            "end": _graph_datetime(event.ends_at),
            # Makes a retried create idempotent on the Graph side.
            "transactionId": f"threecal-{event.booking_id}-{calendar_id}"[:255],
        }
        if event.location:
            payload["location"] = {"displayName": event.location}
        if event.conference == "microsoft_teams":
            payload["isOnlineMeeting"] = True
            payload["onlineMeetingProvider"] = "teamsForBusiness"
        body = self._request_json(
            "POST",
            f"{GRAPH_URL}/me/calendars/{quote(calendar_id, safe='')}/events",
            access_token=access_token,
            json=payload,
        )
        event_id = body.get("id")
        if not isinstance(event_id, str):
            raise ProviderError("Microsoft did not return the created event id.")
        online_meeting = body.get("onlineMeeting") or {}
        join_url = online_meeting.get("joinUrl") if isinstance(online_meeting, dict) else None
        return CalendarEventResult(external_event_id=event_id, meeting_url=str(join_url) if join_url else None)

    def update_event(self, access_token: str, calendar_id: str, event_id: str, event: CalendarEventInput) -> None:
        payload: dict[str, Any] = {
            "start": _graph_datetime(event.starts_at),
            "end": _graph_datetime(event.ends_at),
            "body": {"contentType": "text", "content": event.description},
        }
        if event.location:
            payload["location"] = {"displayName": event.location}
        self._request_json("PATCH", f"{GRAPH_URL}/me/events/{quote(event_id, safe='')}", access_token=access_token, json=payload)

    def delete_event(self, access_token: str, calendar_id: str, event_id: str) -> None:
        response = self._send("DELETE", f"{GRAPH_URL}/me/events/{quote(event_id, safe='')}", access_token=access_token)
        if response.status_code >= 400 and response.status_code not in (404, 410):
            raise self._error(response)
