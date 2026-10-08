"""Provider-agnostic conferencing abstraction.

Standalone conferencing providers (Zoom today; Webex, Whereby, ...) implement
``ConferencingProvider`` and register in ``app.domains.conferencing.providers``.
Google Meet and Microsoft Teams links come from the calendar providers instead,
because they are attached to calendar events.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from app.core.oauth import OAuthHTTPClient, OAuthTokens
from app.domains.conferencing.models import ConferencingProviderName


@dataclass(frozen=True)
class MeetingInput:
    booking_id: str
    topic: str
    agenda: str
    starts_at: datetime
    duration_minutes: int


@dataclass(frozen=True)
class MeetingResult:
    external_meeting_id: str
    join_url: str


class ConferencingProvider(OAuthHTTPClient, ABC):
    name: ClassVar[ConferencingProviderName]

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
    def revoke(self, tokens: OAuthTokens) -> None: ...

    @abstractmethod
    def account_email(self, access_token: str) -> str: ...

    @abstractmethod
    def create_meeting(self, access_token: str, meeting: MeetingInput) -> MeetingResult: ...

    @abstractmethod
    def update_meeting(self, access_token: str, meeting_id: str, meeting: MeetingInput) -> None: ...

    @abstractmethod
    def delete_meeting(self, access_token: str, meeting_id: str) -> None:
        """Deleting a meeting that no longer exists is not an error."""
