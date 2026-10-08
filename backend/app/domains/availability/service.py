import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.availability.models import AvailabilityBreak, AvailabilityException
from app.domains.availability.repository import AvailabilityRepository
from app.domains.availability.schemas import DateOverrideInput
from app.domains.bookings.repository import BookingRepository, as_utc
from app.domains.calendars.busy import get_calendar_busy_intervals
from app.domains.event_types.models import EventType
from app.domains.users.models import User

UTC = ZoneInfo("UTC")
# Upper bound for a single overrides listing, to keep responses small.
MAX_OVERRIDE_RANGE_DAYS = 366


def host_today(user: User) -> date:
    return datetime.now(ZoneInfo(user.timezone)).date()


class AvailabilityService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = AvailabilityRepository(db)

    # Date overrides ----------------------------------------------------------

    def list_overrides(self, user: User, start: date | None, end: date | None) -> list[AvailabilityException]:
        range_start = start or host_today(user)
        range_end = end or range_start + timedelta(days=MAX_OVERRIDE_RANGE_DAYS - 1)
        if range_end < range_start or (range_end - range_start).days >= MAX_OVERRIDE_RANGE_DAYS:
            raise AppError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "invalid_date_range",
                f"Choose a date range of up to {MAX_OVERRIDE_RANGE_DAYS} days.",
            )
        return self.repository.list_exceptions_between(user.id, range_start, range_end)

    def set_override(self, user: User, override_date: date, payload: DateOverrideInput) -> AvailabilityException:
        if override_date < host_today(user):
            raise AppError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "override_in_past",
                "Date overrides can only be set for today or later.",
            )
        row = self.repository.upsert_exception(user.id, override_date, payload)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_override(self, user: User, override_date: date) -> None:
        row = self.repository.get_exception(user.id, override_date)
        if row is None:
            raise AppError(status.HTTP_404_NOT_FOUND, "override_not_found", "No override exists for that date.")
        self.repository.delete_exception(row)
        self.db.commit()

    # Slot generation ---------------------------------------------------------

    def slots(
        self,
        user: User,
        event_type: EventType,
        start_date: date,
        end_date: date,
        viewer_timezone: str,
        exclude_booking_id: uuid.UUID | None = None,
    ) -> list[dict[str, datetime]]:
        """Bookable slots for ``event_type`` between two host-local dates (inclusive).

        Booking creation validates against this method, so every rule here is also
        enforced when a booking is made:

        * Date overrides replace the weekly schedule for their date. An unavailable
          override blocks the day; a custom-hours override replaces the weekly hours
          and the weekly breaks of that weekday do not apply to it.
        * Minimum notice: slots starting before ``now + minimum_notice_minutes`` are dropped.
        * Booking window: host-local dates after ``today + max_days_in_advance`` are dropped.
        * Buffers: existing active bookings are treated as occupying
          ``[start - buffer_before, end + buffer_after]`` and the candidate slot as
          ``[start - buffer_before, end + buffer_after]``, both using this event type's
          buffers. Buffers may extend outside working hours.
        * Daily limit: host-local days that already hold ``daily_booking_limit`` active
          bookings of this event type are dropped.
        * Rescheduling: ``exclude_booking_id`` ignores that booking for conflicts and limits.
        """
        owner_tz = ZoneInfo(user.timezone)
        viewer_tz = ZoneInfo(viewer_timezone)
        now = datetime.now(UTC)
        today = now.astimezone(owner_tz).date()
        # Past days never have slots; days beyond the booking window are not bookable.
        start_date = max(start_date, today)
        if event_type.max_days_in_advance is not None:
            end_date = min(end_date, today + timedelta(days=event_type.max_days_in_advance))
        if end_date < start_date:
            return []

        buffer_before = timedelta(minutes=event_type.buffer_before_minutes or 0)
        buffer_after = timedelta(minutes=event_type.buffer_after_minutes or 0)
        earliest_start = now + timedelta(minutes=event_type.minimum_notice_minutes or 0)
        daily_limit = event_type.daily_booking_limit
        duration = timedelta(minutes=event_type.duration_minutes)
        interval = timedelta(minutes=event_type.slot_interval_minutes)

        hours = {row.weekday: row for row in self.repository.list_hours(user.id) if row.is_enabled}
        exceptions = {row.exception_date: row for row in self.repository.list_exceptions_between(user.id, start_date, end_date)}
        breaks = self.repository.list_breaks([row.id for row in hours.values()])
        breaks_by_hour: dict[uuid.UUID, list[AvailabilityBreak]] = {}
        for item in breaks:
            breaks_by_hour.setdefault(item.working_hour_id, []).append(item)
        range_start = datetime.combine(start_date, datetime.min.time(), owner_tz)
        range_end = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), owner_tz)
        # Pending bookings whose payment window has closed no longer hold their slot.
        # Widen the lookup so bookings just outside the range still block via buffers.
        padding = buffer_before + buffer_after
        bookings = BookingRepository(self.db).list_active_overlapping(user.id, range_start - padding, range_end + padding)
        # A booking being rescheduled must not block its own new time.
        bookings = [booking for booking in bookings if booking.id != exclude_booking_id]
        busy = [(as_utc(booking.starts_at) - buffer_before, as_utc(booking.ends_at) + buffer_after) for booking in bookings]
        # Busy times from the host's connected conflict calendars block slots like bookings do (fails open).
        busy += [(start - buffer_before, end + buffer_after) for start, end in get_calendar_busy_intervals(self.db, user.id, range_start - padding, range_end + padding)]
        bookings_per_day: dict[date, int] = {}
        for booking in bookings:
            if booking.event_type_id == event_type.id:
                booking_day = as_utc(booking.starts_at).astimezone(owner_tz).date()
                bookings_per_day[booking_day] = bookings_per_day.get(booking_day, 0) + 1

        result: list[dict[str, datetime]] = []
        current = start_date
        while current <= end_date:
            if daily_limit is not None and bookings_per_day.get(current, 0) >= daily_limit:
                current += timedelta(days=1)
                continue
            exception = exceptions.get(current)
            if exception and not exception.is_available:
                current += timedelta(days=1)
                continue
            hour = hours.get(current.weekday())
            if exception:
                start_time, end_time = exception.start_time, exception.end_time
                day_breaks: list[AvailabilityBreak] = []
            elif hour:
                start_time, end_time = hour.start_time, hour.end_time
                day_breaks = breaks_by_hour.get(hour.id, [])
            else:
                start_time = end_time = None
                day_breaks = []
            if start_time and end_time:
                cursor = datetime.combine(current, start_time, owner_tz)
                finish = datetime.combine(current, end_time, owner_tz)
                while cursor + duration <= finish:
                    slot_end = cursor + duration
                    in_break = any(cursor.time() < br.end_time and slot_end.time() > br.start_time for br in day_breaks)
                    blocked_start = cursor - buffer_before
                    blocked_end = slot_end + buffer_after
                    conflict = any(blocked_start < busy_end and blocked_end > busy_start for busy_start, busy_end in busy)
                    starts_utc = cursor.astimezone(UTC)
                    if starts_utc > now and starts_utc >= earliest_start and not in_break and not conflict:
                        result.append({"starts_at": cursor.astimezone(viewer_tz), "ends_at": slot_end.astimezone(viewer_tz)})
                    cursor += interval
            current += timedelta(days=1)
        return result
