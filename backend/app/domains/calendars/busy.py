"""Busy times from a host's connected calendars, used by availability to hide conflicting slots."""

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.oauth import ProviderError
from app.domains.calendars import busy_cache
from app.domains.calendars.busy_cache import Interval
from app.domains.calendars.models import CalendarConnection, ConnectionStatus
from app.domains.calendars.providers import get_calendar_provider
from app.domains.calendars.repository import (
    BookingCalendarEventRepository,
    CalendarConnectionRepository,
    SelectedCalendarRepository,
)
from app.domains.calendars.service import CalendarTokenService


logger = logging.getLogger(__name__)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class CalendarBusyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.connections = CalendarConnectionRepository(db)
        self.selected = SelectedCalendarRepository(db)
        self.events = BookingCalendarEventRepository(db)

    def busy_intervals(self, user_id: uuid.UUID, start: datetime, end: datetime) -> list[Interval]:
        """Busy intervals (UTC) overlapping ``[start, end)`` from the host's conflict calendars.

        Fails open: a provider error or timeout is logged and that connection contributes
        no busy times, so a calendar outage never blocks bookings.
        """
        start, end = _utc(start), _utc(end)
        cached = busy_cache.get(user_id, start, end)
        if cached is not None:
            return cached
        calendars = self.selected.conflict_calendars_for_user(user_id)
        if not calendars:
            return []
        by_connection: dict[uuid.UUID, list[str]] = defaultdict(list)
        for row in calendars:
            by_connection[row.connection_id].append(row.external_calendar_id)

        own_ids, own_times = self.events.own_events_in_range(list(by_connection), start, end)
        intervals: list[Interval] = []
        for connection_id, calendar_ids in by_connection.items():
            connection = self.connections.get(connection_id)
            if connection is None or connection.status != ConnectionStatus.ACTIVE.value:
                continue
            for interval in self._fetch(connection, calendar_ids, start, end):
                interval_start, interval_end, event_id = interval
                # Threecal's own booking events are already blocked by the booking itself.
                if (event_id and event_id in own_ids) or (interval_start, interval_end) in own_times:
                    continue
                intervals.append((interval_start, interval_end))
        busy_cache.put(user_id, start, end, intervals)
        return intervals

    def _fetch(
        self,
        connection: CalendarConnection,
        calendar_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> list[tuple[datetime, datetime, str | None]]:
        provider = get_calendar_provider(connection.provider)
        if provider is None or not provider.is_configured():
            return []
        try:
            access_token = CalendarTokenService(self.db).access_token(connection, provider)
            return [
                (_utc(item.start), _utc(item.end), item.external_event_id)
                for item in provider.busy_intervals(access_token, calendar_ids, start, end)
            ]
        except ProviderError:
            logger.warning(
                "calendar busy lookup failed; ignoring calendar conflicts",
                extra={"provider": connection.provider, "connection_id": str(connection.id)},
                exc_info=True,
            )
        except Exception:
            logger.exception("unexpected calendar busy lookup error", extra={"provider": connection.provider})
            self.db.rollback()
        return []


def get_calendar_busy_intervals(db: Session, user_id: uuid.UUID, start: datetime, end: datetime) -> list[Interval]:
    """Entry point for the availability domain; never raises."""
    try:
        return CalendarBusyService(db).busy_intervals(user_id, start, end)
    except Exception:
        logger.exception("calendar busy lookup failed")
        return []
