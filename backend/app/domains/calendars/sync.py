"""Writes confirmed bookings to the host's destination calendar and keeps them in sync."""

import logging
import uuid
from datetime import timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.oauth import ProviderError
from app.domains.bookings.models import Booking, BookingStatus
from app.domains.bookings.repository import as_utc
from app.domains.calendars import busy_cache
from app.domains.calendars.models import BookingCalendarEvent, CalendarConnection, CalendarProviderName, ConnectionStatus
from app.domains.calendars.providers import get_calendar_provider
from app.domains.calendars.providers.base import CalendarEventInput, CalendarProvider, ConferenceKind
from app.domains.calendars.repository import (
    BookingCalendarEventRepository,
    CalendarConnectionRepository,
    SelectedCalendarRepository,
)
from app.domains.calendars.service import CalendarTokenService
from app.domains.event_types.locations import location_text
from app.domains.event_types.models import EventType
from app.domains.users.models import User


logger = logging.getLogger(__name__)

CONFERENCE_PROVIDERS: dict[str, str] = {
    "google_meet": CalendarProviderName.GOOGLE.value,
    "microsoft_teams": CalendarProviderName.MICROSOFT.value,
}


def booking_event_description(booking: Booking, event_type: EventType) -> str:
    lines = [
        f"Booked with Threecal: {event_type.title}",
        "",
        f"Invitee: {booking.invitee_name} <{booking.invitee_email}>",
        f"Invitee timezone: {booking.invitee_timezone}",
    ]
    location = location_text(event_type.location_type, event_type.location_value, booking.meeting_url)
    if location:
        lines.append(f"Location: {location}")
    if booking.notes:
        lines += ["", "Notes from the invitee:", booking.notes]
    lines += ["", f"Manage this booking: {settings.frontend_url.rstrip('/')}/dashboard/bookings"]
    return "\n".join(lines)


class CalendarSyncService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.connections = CalendarConnectionRepository(db)
        self.selected = SelectedCalendarRepository(db)
        self.events = BookingCalendarEventRepository(db)
        self.tokens = CalendarTokenService(db)

    # Event bus entry points ---------------------------------------------------

    def on_confirmed(self, booking_id: uuid.UUID) -> None:
        context = self._context(booking_id)
        if context is None:
            return
        booking, event_type, host = context
        if booking.status != BookingStatus.CONFIRMED:
            return
        destination = self.selected.destination_for_user(host.id)
        if destination is None:
            return
        connection = self.connections.get(destination.connection_id)
        if connection is None or connection.status != ConnectionStatus.ACTIVE.value:
            return
        # Idempotent: the conferencing step may already have created this event (Google Meet / Teams).
        if self.events.find(booking.id, connection.id, destination.external_calendar_id):
            return
        self._create(connection, destination.external_calendar_id, booking, event_type, host, conference=None)

    def on_rescheduled(self, booking_id: uuid.UUID) -> None:
        context = self._context(booking_id)
        if context is None:
            return
        booking, event_type, host = context
        for record in self.events.list_for_booking(booking.id):
            connection = self.connections.get(record.connection_id)
            provider = self._provider(connection)
            if connection is None or provider is None:
                continue
            try:
                provider.update_event(
                    self.tokens.access_token(connection, provider),
                    record.external_calendar_id,
                    record.external_event_id,
                    self._event_input(booking, event_type, host),
                )
            except ProviderError:
                logger.warning("could not update calendar event", extra={"booking_id": str(booking.id), "provider": record.provider}, exc_info=True)
        busy_cache.invalidate(host.id)

    def on_cancelled(self, booking_id: uuid.UUID) -> None:
        booking = self.db.get(Booking, booking_id)
        if booking is None:
            return
        for record in self.events.list_for_booking(booking.id):
            connection = self.connections.get(record.connection_id)
            provider = self._provider(connection)
            if connection is None or provider is None:
                continue
            try:
                provider.delete_event(self.tokens.access_token(connection, provider), record.external_calendar_id, record.external_event_id)
            except ProviderError:
                logger.warning("could not delete calendar event", extra={"booking_id": str(booking.id), "provider": record.provider}, exc_info=True)
                continue
            self.events.delete(record)
            self.db.commit()
        busy_cache.invalidate(booking.host_id)

    # Conferencing support -----------------------------------------------------

    def has_conference_calendar(self, user_id: uuid.UUID, kind: ConferenceKind) -> bool:
        return self.connections.first_active_for_provider(user_id, CONFERENCE_PROVIDERS[kind]) is not None

    def create_conference_event(self, booking: Booking, event_type: EventType, host: User, kind: ConferenceKind) -> str | None:
        """Create the booking's calendar event with a Google Meet / Teams conference and return its join URL.

        Uses the destination calendar when it belongs to the matching provider, so the
        calendar sync step later finds the event and does not create a second one.
        """
        provider_name = CONFERENCE_PROVIDERS[kind]
        destination = self.selected.destination_for_user(host.id)
        connection: CalendarConnection | None = None
        calendar_id: str | None = None
        if destination is not None:
            candidate = self.connections.get(destination.connection_id)
            if candidate is not None and candidate.provider == provider_name and candidate.status == ConnectionStatus.ACTIVE.value:
                connection, calendar_id = candidate, destination.external_calendar_id
        if connection is None:
            connection = self.connections.first_active_for_provider(host.id, provider_name)
        provider = self._provider(connection)
        if connection is None or provider is None:
            logger.warning("no calendar connection for conference", extra={"booking_id": str(booking.id), "conference": kind})
            return None
        if calendar_id is None:
            calendars = provider.list_calendars(self.tokens.access_token(connection, provider))
            primary = next((item for item in calendars if item.is_primary and item.can_write), None)
            if primary is None:
                return None
            calendar_id = primary.id
        if self.events.find(booking.id, connection.id, calendar_id):
            return booking.meeting_url
        return self._create(connection, calendar_id, booking, event_type, host, conference=kind, raise_errors=True)

    # Helpers ------------------------------------------------------------------

    def _create(
        self,
        connection: CalendarConnection,
        calendar_id: str,
        booking: Booking,
        event_type: EventType,
        host: User,
        *,
        conference: ConferenceKind | None,
        raise_errors: bool = False,
    ) -> str | None:
        provider = self._provider(connection)
        if provider is None:
            return None
        try:
            result = provider.create_event(
                self.tokens.access_token(connection, provider),
                calendar_id,
                self._event_input(booking, event_type, host, conference=conference),
            )
        except ProviderError:
            if raise_errors:
                raise
            logger.warning("could not create calendar event", extra={"booking_id": str(booking.id), "provider": connection.provider}, exc_info=True)
            return None
        self.events.add(
            BookingCalendarEvent(
                booking_id=booking.id,
                connection_id=connection.id,
                provider=connection.provider,
                external_calendar_id=calendar_id,
                external_event_id=result.external_event_id,
            )
        )
        try:
            self.db.commit()
        except IntegrityError:
            # A concurrent handler recorded this booking's event first.
            self.db.rollback()
        busy_cache.invalidate(host.id)
        return result.meeting_url

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
    def _provider(connection: CalendarConnection | None) -> CalendarProvider | None:
        if connection is None:
            return None
        provider = get_calendar_provider(connection.provider)
        return provider if provider is not None and provider.is_configured() else None

    @staticmethod
    def _event_input(booking: Booking, event_type: EventType, host: User, conference: ConferenceKind | None = None) -> CalendarEventInput:
        return CalendarEventInput(
            booking_id=str(booking.id),
            title=f"{event_type.title} with {booking.invitee_name}",
            description=booking_event_description(booking, event_type),
            starts_at=as_utc(booking.starts_at).astimezone(timezone.utc),
            ends_at=as_utc(booking.ends_at).astimezone(timezone.utc),
            location=location_text(event_type.location_type, event_type.location_value, booking.meeting_url),
            attendee_email=booking.invitee_email,
            attendee_name=booking.invitee_name,
            conference=conference,
        )
