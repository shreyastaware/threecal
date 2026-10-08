import uuid
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.notifications.models import BookingReminder


class BookingReminderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def sent_booking_ids(self, booking_ids: Iterable[uuid.UUID], offset_minutes: int) -> set[uuid.UUID]:
        ids = list(booking_ids)
        if not ids:
            return set()
        return set(
            self.db.scalars(
                select(BookingReminder.booking_id).where(
                    BookingReminder.booking_id.in_(ids),
                    BookingReminder.offset_minutes == offset_minutes,
                )
            )
        )

    def claim(self, booking_id: uuid.UUID, offset_minutes: int, sent_at: datetime) -> bool:
        """Record the reminder before sending. Returns False if another run already claimed it. Commits."""
        self.db.add(BookingReminder(booking_id=booking_id, offset_minutes=offset_minutes, sent_at=sent_at))
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            return False
        return True

    def release(self, booking_id: uuid.UUID, offset_minutes: int) -> None:
        """Forget a claim whose email failed so a later run can retry it. Commits."""
        self.db.execute(
            delete(BookingReminder).where(
                BookingReminder.booking_id == booking_id,
                BookingReminder.offset_minutes == offset_minutes,
            )
        )
        self.db.commit()

    def reset_for_booking(self, booking_id: uuid.UUID) -> None:
        """Re-arm every reminder after a reschedule. Commits."""
        self.db.execute(delete(BookingReminder).where(BookingReminder.booking_id == booking_id))
        self.db.commit()
