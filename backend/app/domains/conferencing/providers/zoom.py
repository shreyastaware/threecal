"""Zoom provider (user-managed OAuth app).

API references (verified against developers.zoom.us):
- Authorize https://zoom.us/oauth/authorize, token https://zoom.us/oauth/token (HTTP Basic client auth;
  refresh tokens rotate, so the newest one is always stored), revoke https://zoom.us/oauth/revoke.
- GET    /v2/users/me                    account email
- POST   /v2/users/me/meetings           create a scheduled meeting (type 2) -> id, join_url
- PATCH  /v2/meetings/{meetingId}        reschedule (204)
- DELETE /v2/meetings/{meetingId}        delete (204)
Scopes are configured on the Zoom app: meeting:write:meeting, meeting:update:meeting,
meeting:delete:meeting and user:read:user (or classic meeting:write + user:read).
"""

from datetime import timezone
from typing import Any
from urllib.parse import quote, urlencode

from app.core.config import settings
from app.core.oauth import OAuthTokens, ProviderError
from app.domains.conferencing.models import ConferencingProviderName
from app.domains.conferencing.providers.base import ConferencingProvider, MeetingInput, MeetingResult


AUTHORIZE_URL = "https://zoom.us/oauth/authorize"
TOKEN_URL = "https://zoom.us/oauth/token"
REVOKE_URL = "https://zoom.us/oauth/revoke"
API_URL = "https://api.zoom.us/v2"


def _zoom_time(meeting: MeetingInput) -> str:
    return meeting.starts_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ZoomProvider(ConferencingProvider):
    name = ConferencingProviderName.ZOOM

    @property
    def _auth(self) -> tuple[str, str]:
        return (settings.zoom_client_id, settings.zoom_client_secret)

    def is_configured(self) -> bool:
        return bool(settings.zoom_client_id and settings.zoom_client_secret)

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        params = {"response_type": "code", "client_id": settings.zoom_client_id, "redirect_uri": redirect_uri, "state": state}
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code(self, *, code: str, redirect_uri: str) -> OAuthTokens:
        return self._token_request(
            TOKEN_URL,
            {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
            auth=self._auth,
        )

    def refresh(self, refresh_token: str) -> OAuthTokens:
        return self._token_request(
            TOKEN_URL,
            {"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=self._auth,
            previous_refresh_token=refresh_token,
        )

    def revoke(self, tokens: OAuthTokens) -> None:
        self._send("POST", REVOKE_URL, data={"token": tokens.access_token}, auth=self._auth)

    def account_email(self, access_token: str) -> str:
        body = self._request_json("GET", f"{API_URL}/users/me", access_token=access_token)
        email = body.get("email")
        if not isinstance(email, str) or not email:
            raise ProviderError("Zoom did not return the account email.")
        return email.lower()

    def create_meeting(self, access_token: str, meeting: MeetingInput) -> MeetingResult:
        body = self._request_json(
            "POST",
            f"{API_URL}/users/me/meetings",
            access_token=access_token,
            json=self._payload(meeting) | {"type": 2},
        )
        meeting_id, join_url = body.get("id"), body.get("join_url")
        if meeting_id is None or not isinstance(join_url, str):
            raise ProviderError("Zoom did not return the meeting link.")
        # Meeting ids are int64; keep them as strings.
        return MeetingResult(external_meeting_id=str(meeting_id), join_url=join_url)

    def update_meeting(self, access_token: str, meeting_id: str, meeting: MeetingInput) -> None:
        self._request_json("PATCH", f"{API_URL}/meetings/{quote(meeting_id, safe='')}", access_token=access_token, json=self._payload(meeting))

    def delete_meeting(self, access_token: str, meeting_id: str) -> None:
        response = self._send("DELETE", f"{API_URL}/meetings/{quote(meeting_id, safe='')}", access_token=access_token)
        if response.status_code >= 400 and response.status_code != 404:
            raise self._error(response)

    @staticmethod
    def _payload(meeting: MeetingInput) -> dict[str, Any]:
        return {
            "topic": meeting.topic[:200],
            "start_time": _zoom_time(meeting),
            "duration": meeting.duration_minutes,
            "timezone": "UTC",
            "agenda": meeting.agenda[:2000],
        }
