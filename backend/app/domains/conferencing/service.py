import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.oauth import (
    OAuthStateError,
    ProviderError,
    ReconnectRequiredError,
    create_oauth_state,
    frontend_integrations_url,
    oauth_redirect_uri,
    verify_oauth_state,
)
from app.domains.bookings.models import Booking, BookingStatus
from app.domains.bookings.repository import as_utc
from app.domains.calendars.sync import CalendarSyncService, booking_event_description
from app.domains.conferencing.models import BookingMeeting, ConferencingConnection, ConferencingProviderName
from app.domains.conferencing.providers import get_conferencing_provider
from app.domains.conferencing.providers.base import ConferencingProvider, MeetingInput
from app.domains.conferencing.repository import BookingMeetingRepository, ConferencingConnectionRepository
from app.domains.conferencing.schemas import AuthorizationUrlRead, ConferencingConnectionRead
from app.domains.event_types.models import EventType, LocationType
from app.domains.users.models import User


logger = logging.getLogger(__name__)

OAUTH_KIND = "conferencing"
ACTIVE = "active"
RECONNECT_REQUIRED = "reconnect_required"
TOKEN_REFRESH_MARGIN = timedelta(seconds=60)


def conferencing_redirect_uri(provider: str) -> str:
    return oauth_redirect_uri(f"/conferencing/oauth/{provider}/callback")


def require_provider(name: str) -> ConferencingProvider:
    provider = get_conferencing_provider(name)
    if provider is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "conferencing_provider_not_found", "Unknown conferencing provider.")
    if not provider.is_configured():
        raise AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "not_configured",
            "This conferencing integration is not available yet. Please try again later.",
        )
    return provider


def ensure_location_available(db: Session, user_id: uuid.UUID, location_type: str) -> None:
    """Reject online locations whose integration is not connected (used when saving event types)."""
    calendars = CalendarSyncService(db)
    if location_type == LocationType.GOOGLE_MEET.value and not calendars.has_conference_calendar(user_id, "google_meet"):
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "google_calendar_required",
            "Connect Google Calendar in Integrations before using Google Meet as the location.",
        )
    if location_type == LocationType.MICROSOFT_TEAMS.value and not calendars.has_conference_calendar(user_id, "microsoft_teams"):
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "outlook_calendar_required",
            "Connect Outlook Calendar in Integrations before using Microsoft Teams as the location.",
        )
    if location_type == LocationType.ZOOM.value:
        connection = ConferencingConnectionRepository(db).get_for_provider(user_id, ConferencingProviderName.ZOOM.value)
        if connection is None or connection.status != ACTIVE:
            raise AppError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "zoom_connection_required",
                "Connect Zoom in Integrations before using Zoom as the location.",
            )


class ConferencingTokenService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def access_token(self, connection: ConferencingConnection, provider: ConferencingProvider) -> str:
        if connection.status == RECONNECT_REQUIRED:
            raise ReconnectRequiredError("Conferencing connection needs to be reconnected.")
        tokens = ConferencingConnectionRepository.tokens(connection)
        expires_at = as_utc(tokens.expires_at) if tokens.expires_at else None
        if expires_at is None or expires_at > datetime.now(timezone.utc) + TOKEN_REFRESH_MARGIN:
            return tokens.access_token
        if not tokens.refresh_token:
            self._mark_reconnect_required(connection)
            raise ReconnectRequiredError("Conferencing connection has no refresh token.")
        try:
            refreshed = provider.refresh(tokens.refresh_token)
        except ReconnectRequiredError:
            self._mark_reconnect_required(connection)
            raise
        # Zoom rotates refresh tokens: persist the new one immediately.
        ConferencingConnectionRepository.set_tokens(connection, refreshed)
        self.db.commit()
        return refreshed.access_token

    def _mark_reconnect_required(self, connection: ConferencingConnection) -> None:
        connection.status = RECONNECT_REQUIRED
        self.db.commit()
        logger.warning("conferencing connection needs reconnection", extra={"connection_id": str(connection.id), "provider": connection.provider})


class ConferencingConnectionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.connections = ConferencingConnectionRepository(db)

    def list_connections(self, user: User) -> list[ConferencingConnectionRead]:
        return [ConferencingConnectionRead.model_validate(item) for item in self.connections.list_for_user(user.id)]

    def authorization_url(self, user: User, provider_name: str) -> AuthorizationUrlRead:
        provider = require_provider(provider_name)
        state = create_oauth_state(user.id, kind=OAUTH_KIND, provider=provider_name)
        return AuthorizationUrlRead(
            authorization_url=provider.authorization_url(state=state, redirect_uri=conferencing_redirect_uri(provider_name))
        )

    def complete_oauth(self, provider_name: str, *, code: str | None, state: str | None, error: str | None) -> str:
        provider = get_conferencing_provider(provider_name)
        if provider is None or not provider.is_configured():
            return frontend_integrations_url(error="not_configured")
        try:
            user_id = verify_oauth_state(state, kind=OAUTH_KIND, provider=provider_name)
        except OAuthStateError:
            return frontend_integrations_url(error="invalid_state")
        if error or not code:
            return frontend_integrations_url(error=error or "access_denied")
        try:
            tokens = provider.exchange_code(code=code, redirect_uri=conferencing_redirect_uri(provider_name))
            email = provider.account_email(tokens.access_token)
        except ProviderError:
            logger.exception("conferencing oauth exchange failed", extra={"provider": provider_name})
            return frontend_integrations_url(error="connection_failed")
        # One connection per provider: reconnecting (even with another account) replaces it.
        connection = self.connections.get_for_provider(user_id, provider_name)
        if connection is None:
            connection = ConferencingConnection(user_id=user_id, provider=provider_name, account_email=email, encrypted_access_token="")
            ConferencingConnectionRepository.set_tokens(connection, tokens)
            self.connections.add(connection)
        else:
            connection.account_email = email
            ConferencingConnectionRepository.set_tokens(connection, tokens)
            connection.status = ACTIVE
        self.db.commit()
        return frontend_integrations_url(connected=provider_name)

    def delete_connection(self, user: User, connection_id: uuid.UUID) -> None:
        connection = self.connections.get_for_user(connection_id, user.id)
        if connection is None:
            raise AppError(status.HTTP_404_NOT_FOUND, "conferencing_connection_not_found", "Conferencing connection not found.")
        provider = get_conferencing_provider(connection.provider)
        if provider is not None and provider.is_configured():
            try:
                provider.revoke(ConferencingConnectionRepository.tokens(connection))
            except Exception:
                # Best effort: the stored tokens are deleted either way.
                logger.warning("conferencing token revocation failed", extra={"provider": connection.provider}, exc_info=True)
        self.connections.delete(connection)
        self.db.commit()


class MeetingService:
    """Creates, moves and removes meeting links for bookings based on the event type location."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.connections = ConferencingConnectionRepository(db)
        self.meetings = BookingMeetingRepository(db)
        self.tokens = ConferencingTokenService(db)

    def on_confirmed(self, booking_id: uuid.UUID) -> None:
        context = self._context(booking_id)
        if context is None:
            return
        booking, event_type, host = context
        # Idempotent: a link set earlier (or a retried event) is kept as is.
        if booking.status != BookingStatus.CONFIRMED or booking.meeting_url:
            return
        location = event_type.location_type or LocationType.NONE.value
        meeting_url: str | None = None
        try:
            if location == LocationType.CUSTOM_LINK.value:
                meeting_url = event_type.location_value
            elif location == LocationType.GOOGLE_MEET.value:
                meeting_url = CalendarSyncService(self.db).create_conference_event(booking, event_type, host, "google_meet")
            elif location == LocationType.MICROSOFT_TEAMS.value:
                meeting_url = CalendarSyncService(self.db).create_conference_event(booking, event_type, host, "microsoft_teams")
            elif location == LocationType.ZOOM.value:
                meeting_url = self._create_zoom_meeting(booking, event_type, host)
        except ProviderError:
            # The booking stays confirmed; it just has no generated link.
            logger.warning("could not create meeting link", extra={"booking_id": str(booking.id), "location": location}, exc_info=True)
            self.db.rollback()
            return
        if meeting_url:
            booking = self.db.get(Booking, booking_id) or booking
            booking.meeting_url = meeting_url
            self.db.commit()

    def on_rescheduled(self, booking_id: uuid.UUID) -> None:
        context = self._context(booking_id)
        if context is None:
            return
        booking, event_type, host = context
        record = self.meetings.get_for_booking(booking.id)
        if record is None:
            return
        connection, provider = self._connection_for(record)
        if connection is None or provider is None:
            return
        try:
            provider.update_meeting(self.tokens.access_token(connection, provider), record.external_meeting_id, self._meeting_input(booking, event_type, host))
        except ProviderError:
            logger.warning("could not update meeting", extra={"booking_id": str(booking.id), "provider": record.provider}, exc_info=True)

    def on_cancelled(self, booking_id: uuid.UUID) -> None:
        record = self.meetings.get_for_booking(booking_id)
        if record is None:
            return
        connection, provider = self._connection_for(record)
        if connection is None or provider is None:
            return
        try:
            provider.delete_meeting(self.tokens.access_token(connection, provider), record.external_meeting_id)
        except ProviderError:
            logger.warning("could not delete meeting", extra={"booking_id": str(booking_id), "provider": record.provider}, exc_info=True)
            return
        self.meetings.delete(record)
        self.db.commit()

    def _create_zoom_meeting(self, booking: Booking, event_type: EventType, host: User) -> str | None:
        existing = self.meetings.get_for_booking(booking.id)
        if existing is not None:
            return existing.join_url
        connection = self.connections.get_for_provider(host.id, ConferencingProviderName.ZOOM.value)
        provider = get_conferencing_provider(ConferencingProviderName.ZOOM.value)
        if connection is None or provider is None or not provider.is_configured():
            logger.warning("zoom location without a zoom connection", extra={"booking_id": str(booking.id)})
            return None
        result = provider.create_meeting(self.tokens.access_token(connection, provider), self._meeting_input(booking, event_type, host))
        self.meetings.add(
            BookingMeeting(
                booking_id=booking.id,
                connection_id=connection.id,
                provider=connection.provider,
                external_meeting_id=result.external_meeting_id,
                join_url=result.join_url,
            )
        )
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
        return result.join_url

    def _connection_for(self, record: BookingMeeting) -> tuple[ConferencingConnection | None, ConferencingProvider | None]:
        connection = self.connections.get(record.connection_id)
        provider = get_conferencing_provider(record.provider)
        if provider is None or not provider.is_configured():
            return connection, None
        return connection, provider

    def _context(self, booking_id: uuid.UUID) -> tuple[Booking, EventType, User] | None:
        booking = self.db.get(Booking, booking_id)
        if booking is None:
            return None
        event_type = self.db.get(EventType, booking.event_type_id)
        host = self.db.get(User, booking.host_id)
        if event_type is None or host is None:
            return None
        return booking, event_type, host

    @staticmethod
    def _meeting_input(booking: Booking, event_type: EventType, host: User) -> MeetingInput:
        starts_at = as_utc(booking.starts_at)
        duration = int((as_utc(booking.ends_at) - starts_at).total_seconds() // 60) or event_type.duration_minutes
        return MeetingInput(
            booking_id=str(booking.id),
            topic=f"{event_type.title} with {booking.invitee_name}",
            agenda=booking_event_description(booking, event_type),
            starts_at=starts_at,
            duration_minutes=duration,
        )
