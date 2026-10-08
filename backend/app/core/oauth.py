"""Shared building blocks for third-party OAuth integrations (calendars, conferencing).

* Signed, expiring OAuth ``state`` values that bind the flow to a Threecal user,
  an integration kind and a provider, so a callback cannot be replayed for
  another account or provider.
* ``OAuthHTTPClient``: a tiny httpx wrapper with a shared timeout, normalized
  errors and a class-level ``transport`` hook that tests replace with an
  ``httpx.MockTransport``.
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar

import httpx
from jose import JWTError, jwt  # type: ignore[import-untyped]

from app.core.config import settings


OAUTH_STATE_TTL = timedelta(minutes=15)
RECONNECT_ERROR_CODES = {"invalid_grant", "interaction_required"}
_STATE_TYPE = "integration_oauth_state"


class OAuthStateError(ValueError):
    """The OAuth state is missing, tampered with, expired or for another flow."""


def create_oauth_state(user_id: uuid.UUID, *, kind: str, provider: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": _STATE_TYPE,
        "kind": kind,
        "provider": provider,
        # Makes every state unique even when started twice in the same second.
        "nonce": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + OAUTH_STATE_TTL,
    }
    return str(jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm))


def verify_oauth_state(state: str | None, *, kind: str, provider: str) -> uuid.UUID:
    """Return the user id the state was issued for, or raise ``OAuthStateError``."""
    if not state:
        raise OAuthStateError("Missing OAuth state.")
    try:
        claims = jwt.decode(state, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise OAuthStateError("Invalid or expired OAuth state.") from exc
    if claims.get("type") != _STATE_TYPE or claims.get("kind") != kind or claims.get("provider") != provider:
        raise OAuthStateError("OAuth state does not match this integration.")
    try:
        return uuid.UUID(str(claims.get("sub")))
    except ValueError as exc:
        raise OAuthStateError("Invalid OAuth state subject.") from exc


def oauth_redirect_uri(path: str) -> str:
    """Absolute callback URL registered with the provider, e.g. ``/calendars/oauth/google/callback``."""
    return f"{settings.public_api_url.rstrip('/')}{settings.api_v1_prefix}{path}"


def frontend_integrations_url(**params: str) -> str:
    query = str(httpx.QueryParams(params))
    base = f"{settings.frontend_url.rstrip('/')}/dashboard/integrations"
    return f"{base}?{query}" if query else base


@dataclass(frozen=True)
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scope: str | None = None


class ProviderError(RuntimeError):
    """A provider API call failed (network error, timeout or non-2xx response)."""

    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class ReconnectRequiredError(ProviderError):
    """The stored refresh token was revoked or expired (``invalid_grant``); the user must reconnect."""


def tokens_from_response(payload: dict[str, Any], *, previous_refresh_token: str | None = None) -> OAuthTokens:
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise ProviderError("Token response did not include an access token.")
    expires_in = payload.get("expires_in")
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        if isinstance(expires_in, (int, float, str)) and str(expires_in).isdigit()
        else None
    )
    refresh_token = payload.get("refresh_token")
    return OAuthTokens(
        access_token=access_token,
        # Google omits the refresh token on refresh; keep the one we already have.
        refresh_token=refresh_token if isinstance(refresh_token, str) and refresh_token else previous_refresh_token,
        expires_at=expires_at,
        scope=payload.get("scope") if isinstance(payload.get("scope"), str) else None,
    )


class OAuthHTTPClient:
    """Base class for provider clients. Tests set ``OAuthHTTPClient.transport``."""

    transport: ClassVar[httpx.BaseTransport | None] = None
    timeout_seconds: ClassVar[float] = 8.0

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout_seconds, transport=OAuthHTTPClient.transport)

    def _send(
        self,
        method: str,
        url: str,
        *,
        access_token: str | None = None,
        json: Any = None,
        data: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
    ) -> httpx.Response:
        request_headers = {"Accept": "application/json", **(headers or {})}
        if access_token:
            request_headers["Authorization"] = f"Bearer {access_token}"
        try:
            with self._client() as client:
                response = client.request(
                    method,
                    url,
                    json=json,
                    data=data,
                    params=params,
                    headers=request_headers,
                    auth=auth,
                )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Could not reach provider: {exc.__class__.__name__}") from exc
        return response

    def _request_json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        response = self._send(method, url, **kwargs)
        if response.status_code >= 400:
            raise self._error(response)
        if response.status_code == 204 or not response.content:
            return {}
        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderError("Provider returned an invalid response.", status_code=response.status_code) from exc
        return body if isinstance(body, dict) else {"value": body}

    def _token_request(
        self,
        url: str,
        data: dict[str, str],
        *,
        auth: tuple[str, str] | None = None,
        previous_refresh_token: str | None = None,
    ) -> OAuthTokens:
        response = self._send("POST", url, data=data, auth=auth)
        if response.status_code >= 400:
            error = self._error(response)
            # Microsoft returns interaction_required when consent/MFA must be repeated.
            if error.code in RECONNECT_ERROR_CODES:
                raise ReconnectRequiredError(str(error), status_code=error.status_code, code=error.code)
            raise error
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("Provider returned an invalid token response.") from exc
        return tokens_from_response(payload, previous_refresh_token=previous_refresh_token)

    @staticmethod
    def _error(response: httpx.Response) -> ProviderError:
        code: str | None = None
        message = f"Provider request failed with status {response.status_code}."
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            raw_error = body.get("error")
            if isinstance(raw_error, str):
                code = raw_error
                description = body.get("error_description") or body.get("reason")
                if isinstance(description, str):
                    message = description
            elif isinstance(raw_error, dict):
                raw_code = raw_error.get("code") or raw_error.get("status")
                code = str(raw_code) if raw_code is not None else None
                if isinstance(raw_error.get("message"), str):
                    message = raw_error["message"]
            elif isinstance(body.get("message"), str):
                message = body["message"]
                code = str(body.get("code")) if body.get("code") is not None else None
        return ProviderError(message, status_code=response.status_code, code=code)
