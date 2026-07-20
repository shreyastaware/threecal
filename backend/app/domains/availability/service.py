import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.availability.models import AvailabilityBreak
from app.domains.availability.repository import AvailabilityRepository
from app.domains.bookings.models import Booking, BookingStatus
from app.domains.event_types.models import EventType
from app.domains.users.models import User


class AvailabilityService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = AvailabilityRepository(db)

    def slots(self, user: User, event_type: EventType, start_date: date, end_date: date, viewer_timezone: str) -> list[dict[str, datetime]]:
        owner_tz = ZoneInfo(user.timezone)
        viewer_tz = ZoneInfo(viewer_timezone)
        hours = {row.weekday: row for row in self.repository.list_hours(user.id) if row.is_enabled}
        exceptions = {row.exception_date: row for row in self.repository.list_exceptions(user.id)}
        breaks = self.repository.list_breaks([row.id for row in hours.values()])
        breaks_by_hour: dict[uuid.UUID, list[AvailabilityBreak]] = {}
        for item in breaks:
            breaks_by_hour.setdefault(item.working_hour_id, []).append(item)
        range_start = datetime.combine(start_date, datetime.min.time(), owner_tz)
        range_end = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), owner_tz)
        bookings = list(self.db.scalars(select(Booking).where(Booking.host_id == user.id, Booking.starts_at < range_end, Booking.ends_at > range_start, Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]))))
        result: list[dict[str, datetime]] = []
        current = start_date
        now = datetime.now(ZoneInfo("UTC"))
        while current <= end_date:
            exception = exceptions.get(current)
            hour = hours.get(current.weekday())
            if exception and not exception.is_available:
                current += timedelta(days=1)
                continue
            start_time = exception.start_time if exception and exception.is_available else hour.start_time if hour else None
            end_time = exception.end_time if exception and exception.is_available else hour.end_time if hour else None
            if start_time and end_time:
                cursor = datetime.combine(current, start_time, owner_tz)
                finish = datetime.combine(current, end_time, owner_tz)
                duration = timedelta(minutes=event_type.duration_minutes)
                while cursor + duration <= finish:
                    slot_end = cursor + duration
                    in_break = bool(hour and any(cursor.time() < br.end_time and slot_end.time() > br.start_time for br in breaks_by_hour.get(hour.id, [])))
                    conflict = any(cursor < booking.ends_at.astimezone(owner_tz) and slot_end > booking.starts_at.astimezone(owner_tz) for booking in bookings)
                    if cursor.astimezone(ZoneInfo("UTC")) > now and not in_break and not conflict:
                        result.append({"starts_at": cursor.astimezone(viewer_tz), "ends_at": slot_end.astimezone(viewer_tz)})
                    cursor += timedelta(minutes=event_type.slot_interval_minutes)
            current += timedelta(days=1)
        return result
