"""Provider-agnostic calendar abstraction.

New calendar providers (Apple/CalDAV, ...) plug in by implementing
``CalendarProvider`` and registering in ``app.domains.calendars.providers``.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal

from app.core.oauth import OAuthHTTPClient, OAuthTokens
from app.domains.calendars.models import CalendarProviderName


ConferenceKind = Literal["google_meet", "microsoft_teams"]


@dataclass(frozen=True)
class ProviderCalendar:
    id: str
    name: str
    is_primary: bool
    can_write: bool


@dataclass(frozen=True)
class BusyInterval:
    start: datetime
    end: datetime
    # Set when the provider reports individual events, so Threecal's own events can be skipped.
    external_event_id: str | None = None


@dataclass(frozen=True)
class CalendarEventInput:
    booking_id: str
    title: str
    description: str
    starts_at: datetime
    ends_at: datetime
    location: str | None
    attendee_email: str
    attendee_name: str
    # Ask the provider to attach a conference (Google Meet / Teams) to the event.
    conference: ConferenceKind | None = None


@dataclass(frozen=True)
class CalendarEventResult:
    external_event_id: str
    meeting_url: str | None = None


class CalendarProvider(OAuthHTTPClient, ABC):
    name: ClassVar[CalendarProviderName]
    # The conference type this provider can create on its own events, if any.
    conference: ClassVar[ConferenceKind | None] = None

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def authorization_url(self, *, state: str, redirect_uri: str) -> str: ...

    @abstractmethod
    def exchange_code(self, *, code: str, redirect_uri: str) -> OAuthTokens: ...

    @abstractmethod
    def refresh(self, refresh_token: str) -> OAuthTokens:
        """Raise ``ReconnectRequiredError`` when the refresh token is no longer valid."""

    @abstractmethod
    def revoke(self, tokens: OAuthTokens) -> None:
        """Best effort; providers without a revocation endpoint do nothing."""

    @abstractmethod
    def account_email(self, access_token: str) -> str: ...

    @abstractmethod
    def list_calendars(self, access_token: str) -> list[ProviderCalendar]: ...

    @abstractmethod
    def busy_intervals(self, access_token: str, calendar_ids: list[str], start: datetime, end: datetime) -> list[BusyInterval]: ...

    @abstractmethod
    def create_event(self, access_token: str, calendar_id: str, event: CalendarEventInput) -> CalendarEventResult: ...

    @abstractmethod
    def update_event(self, access_token: str, calendar_id: str, event_id: str, event: CalendarEventInput) -> None: ...

    @abstractmethod
    def delete_event(self, access_token: str, calendar_id: str, event_id: str) -> None:
        """Deleting an event that no longer exists is not an error."""
