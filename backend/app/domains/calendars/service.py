import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import status
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
from app.domains.calendars import busy_cache
from app.domains.calendars.models import CalendarConnection, ConnectionStatus, SelectedCalendar
from app.domains.calendars.providers import get_calendar_provider
from app.domains.calendars.providers.base import CalendarProvider, ProviderCalendar
from app.domains.calendars.repository import CalendarConnectionRepository, SelectedCalendarRepository
from app.domains.calendars.schemas import (
    AuthorizationUrlRead,
    CalendarConnectionRead,
    CalendarConnectionUpdate,
    ProviderCalendarRead,
)
from app.domains.users.models import User


logger = logging.getLogger(__name__)

OAUTH_KIND = "calendar"
# Refresh access tokens this long before they expire.
TOKEN_REFRESH_MARGIN = timedelta(seconds=60)


def calendar_redirect_uri(provider: str) -> str:
    return oauth_redirect_uri(f"/calendars/oauth/{provider}/callback")


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def require_provider(name: str, *, configured: bool = True) -> CalendarProvider:
    provider = get_calendar_provider(name)
    if provider is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "calendar_provider_not_found", "Unknown calendar provider.")
    if configured and not provider.is_configured():
        raise AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "not_configured",
            "This calendar integration is not available yet. Please try again later.",
        )
    return provider


class CalendarTokenService:
    """Returns valid access tokens, refreshing them and flagging revoked connections."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def access_token(self, connection: CalendarConnection, provider: CalendarProvider) -> str:
        if connection.status == ConnectionStatus.RECONNECT_REQUIRED.value:
            raise ReconnectRequiredError("Calendar connection needs to be reconnected.")
        tokens = CalendarConnectionRepository.tokens(connection)
        if tokens.expires_at is None or _as_utc(tokens.expires_at) > datetime.now(timezone.utc) + TOKEN_REFRESH_MARGIN:
            return tokens.access_token
        if not tokens.refresh_token:
            self._mark_reconnect_required(connection)
            raise ReconnectRequiredError("Calendar connection has no refresh token.")
        try:
            refreshed = provider.refresh(tokens.refresh_token)
        except ReconnectRequiredError:
            self._mark_reconnect_required(connection)
            raise
        CalendarConnectionRepository.set_tokens(connection, refreshed)
        self.db.commit()
        return refreshed.access_token

    def _mark_reconnect_required(self, connection: CalendarConnection) -> None:
        connection.status = ConnectionStatus.RECONNECT_REQUIRED.value
        self.db.commit()
        busy_cache.invalidate(connection.user_id)
        logger.warning("calendar connection needs reconnection", extra={"connection_id": str(connection.id), "provider": connection.provider})


class CalendarConnectionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.connections = CalendarConnectionRepository(db)
        self.selected = SelectedCalendarRepository(db)
        self.tokens = CalendarTokenService(db)

    # OAuth ------------------------------------------------------------------

    def authorization_url(self, user: User, provider_name: str) -> AuthorizationUrlRead:
        provider = require_provider(provider_name)
        state = create_oauth_state(user.id, kind=OAUTH_KIND, provider=provider_name)
        return AuthorizationUrlRead(
            authorization_url=provider.authorization_url(state=state, redirect_uri=calendar_redirect_uri(provider_name))
        )

    def complete_oauth(self, provider_name: str, *, code: str | None, state: str | None, error: str | None) -> str:
        """Finish the OAuth callback and return the frontend URL to redirect to."""
        provider = get_calendar_provider(provider_name)
        if provider is None or not provider.is_configured():
            return frontend_integrations_url(error="not_configured")
        try:
            user_id = verify_oauth_state(state, kind=OAUTH_KIND, provider=provider_name)
        except OAuthStateError:
            return frontend_integrations_url(error="invalid_state")
        if error or not code:
            return frontend_integrations_url(error=error or "access_denied")
        try:
            tokens = provider.exchange_code(code=code, redirect_uri=calendar_redirect_uri(provider_name))
            email = provider.account_email(tokens.access_token)
        except ProviderError:
            logger.exception("calendar oauth exchange failed", extra={"provider": provider_name})
            return frontend_integrations_url(error="connection_failed")

        connection = self.connections.get_by_account(user_id, provider_name, email)
        is_new = connection is None
        if connection is None:
            connection = CalendarConnection(user_id=user_id, provider=provider_name, account_email=email, encrypted_access_token="")
            CalendarConnectionRepository.set_tokens(connection, tokens)
            self.connections.add(connection)
        else:
            CalendarConnectionRepository.set_tokens(connection, tokens)
            connection.status = ConnectionStatus.ACTIVE.value
        self.db.commit()
        if is_new:
            self._select_defaults(connection, provider, tokens.access_token)
        busy_cache.invalidate(user_id)
        return frontend_integrations_url(connected=provider_name)

    def _select_defaults(self, connection: CalendarConnection, provider: CalendarProvider, access_token: str) -> None:
        """Check the primary calendar for conflicts and write bookings to it if no destination exists yet."""
        try:
            calendars = provider.list_calendars(access_token)
        except ProviderError:
            logger.exception("could not list calendars after connecting", extra={"provider": connection.provider})
            return
        primary = next((item for item in calendars if item.is_primary), None)
        if primary is None:
            return
        make_destination = primary.can_write and self.selected.destination_for_user(connection.user_id) is None
        self.selected.replace_for_connection(
            connection,
            [
                SelectedCalendar(
                    connection_id=connection.id,
                    user_id=connection.user_id,
                    external_calendar_id=primary.id,
                    name=primary.name[:255],
                    check_conflicts=True,
                    is_destination=make_destination,
                )
            ],
        )
        self.db.commit()

    # Connections --------------------------------------------------------------

    def list_connections(self, user: User) -> list[CalendarConnectionRead]:
        return [self._to_read(connection) for connection in self.connections.list_for_user(user.id)]

    def list_calendars(self, user: User, connection_id: uuid.UUID) -> list[ProviderCalendarRead]:
        connection = self._get(user, connection_id)
        calendars = self._provider_calendars(connection)
        selected = {row.external_calendar_id: row for row in self.selected.list_for_connection(connection.id)}
        return [
            ProviderCalendarRead(
                id=item.id,
                name=item.name,
                is_primary=item.is_primary,
                can_write=item.can_write,
                check_conflicts=bool(selected.get(item.id) and selected[item.id].check_conflicts),
                is_destination=bool(selected.get(item.id) and selected[item.id].is_destination),
            )
            for item in calendars
        ]

    def update_connection(self, user: User, connection_id: uuid.UUID, payload: CalendarConnectionUpdate) -> CalendarConnectionRead:
        connection = self._get(user, connection_id)
        calendars = {item.id: item for item in self._provider_calendars(connection)}
        conflict_ids = list(dict.fromkeys(payload.conflict_calendar_ids))
        unknown = [calendar_id for calendar_id in conflict_ids if calendar_id not in calendars]
        if unknown:
            raise AppError(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_calendar", "One of the selected calendars no longer exists.")
        destination_id = payload.destination_calendar_id
        if destination_id is not None:
            destination = calendars.get(destination_id)
            if destination is None:
                raise AppError(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_calendar", "The destination calendar no longer exists.")
            if not destination.can_write:
                raise AppError(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "calendar_read_only",
                    "Threecal can't add events to that calendar. Choose a calendar you can edit.",
                )
            # One destination per host across all connections.
            self.selected.clear_destination(user.id)
        rows = [
            SelectedCalendar(
                connection_id=connection.id,
                user_id=user.id,
                external_calendar_id=calendar_id,
                name=calendars[calendar_id].name[:255],
                check_conflicts=calendar_id in conflict_ids,
                is_destination=calendar_id == destination_id,
            )
            for calendar_id in dict.fromkeys([*conflict_ids, *([destination_id] if destination_id else [])])
        ]
        self.selected.replace_for_connection(connection, rows)
        self.db.commit()
        busy_cache.invalidate(user.id)
        return self._to_read(connection)

    def delete_connection(self, user: User, connection_id: uuid.UUID) -> None:
        connection = self._get(user, connection_id)
        provider = get_calendar_provider(connection.provider)
        if provider is not None and provider.is_configured():
            try:
                provider.revoke(CalendarConnectionRepository.tokens(connection))
            except Exception:
                # Best effort: the stored tokens are deleted either way.
                logger.warning("calendar token revocation failed", extra={"provider": connection.provider}, exc_info=True)
        self.connections.delete(connection)
        self.db.commit()
        busy_cache.invalidate(user.id)

    # Helpers ------------------------------------------------------------------

    def _get(self, user: User, connection_id: uuid.UUID) -> CalendarConnection:
        connection = self.connections.get_for_user(connection_id, user.id)
        if connection is None:
            raise AppError(status.HTTP_404_NOT_FOUND, "calendar_connection_not_found", "Calendar connection not found.")
        return connection

    def _provider_calendars(self, connection: CalendarConnection) -> list[ProviderCalendar]:
        provider = require_provider(connection.provider)
        try:
            return provider.list_calendars(self.tokens.access_token(connection, provider))
        except ReconnectRequiredError as exc:
            raise AppError(
                status.HTTP_409_CONFLICT,
                "reconnect_required",
                "This calendar connection has expired. Reconnect it to continue.",
            ) from exc
        except ProviderError as exc:
            raise AppError(
                status.HTTP_502_BAD_GATEWAY,
                "calendar_provider_unavailable",
                "We couldn't load your calendars right now. Please try again.",
            ) from exc

    def _to_read(self, connection: CalendarConnection) -> CalendarConnectionRead:
        selected = self.selected.list_for_connection(connection.id)
        return CalendarConnectionRead(
            id=connection.id,
            provider=connection.provider,
            account_email=connection.account_email,
            status=connection.status,
            created_at=connection.created_at,
            conflict_calendar_ids=[row.external_calendar_id for row in selected if row.check_conflicts],
            destination_calendar_id=next((row.external_calendar_id for row in selected if row.is_destination), None),
        )
