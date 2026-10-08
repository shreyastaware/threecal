import uuid
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domains.availability.models import AvailabilityBreak, AvailabilityException, WorkingHour
from app.domains.availability.schemas import DateOverrideInput, ScheduleReplace


class AvailabilityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_hours(self, user_id: uuid.UUID) -> list[WorkingHour]:
        return list(self.db.scalars(select(WorkingHour).where(WorkingHour.user_id == user_id).order_by(WorkingHour.weekday)))

    def list_breaks(self, hour_ids: list[uuid.UUID]) -> list[AvailabilityBreak]:
        if not hour_ids:
            return []
        return list(self.db.scalars(select(AvailabilityBreak).where(AvailabilityBreak.working_hour_id.in_(hour_ids))))

    def replace(self, user_id: uuid.UUID, payload: ScheduleReplace) -> list[WorkingHour]:
        old_ids = [row.id for row in self.list_hours(user_id)]
        if old_ids:
            self.db.execute(delete(AvailabilityBreak).where(AvailabilityBreak.working_hour_id.in_(old_ids)))
        self.db.execute(delete(WorkingHour).where(WorkingHour.user_id == user_id))
        for item in payload.working_hours:
            hour = WorkingHour(user_id=user_id, **item.model_dump(exclude={"breaks"}))
            self.db.add(hour)
            self.db.flush()
            self.db.add_all([AvailabilityBreak(working_hour_id=hour.id, **br.model_dump()) for br in item.breaks])
        self.db.commit()
        return self.list_hours(user_id)

    def list_exceptions(self, user_id: uuid.UUID) -> list[AvailabilityException]:
        return list(self.db.scalars(select(AvailabilityException).where(AvailabilityException.user_id == user_id)))

    def list_exceptions_between(self, user_id: uuid.UUID, start: date, end: date) -> list[AvailabilityException]:
        return list(
            self.db.scalars(
                select(AvailabilityException)
                .where(
                    AvailabilityException.user_id == user_id,
                    AvailabilityException.exception_date >= start,
                    AvailabilityException.exception_date <= end,
                )
                .order_by(AvailabilityException.exception_date)
            )
        )

    def get_exception(self, user_id: uuid.UUID, exception_date: date) -> AvailabilityException | None:
        return self.db.scalar(
            select(AvailabilityException).where(
                AvailabilityException.user_id == user_id,
                AvailabilityException.exception_date == exception_date,
            )
        )

    def upsert_exception(self, user_id: uuid.UUID, exception_date: date, payload: DateOverrideInput) -> AvailabilityException:
        # One override per date: setting a date again replaces the previous override.
        row = self.get_exception(user_id, exception_date)
        if row is None:
            row = AvailabilityException(user_id=user_id, exception_date=exception_date)
            self.db.add(row)
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
        return row

    def delete_exception(self, row: AvailabilityException) -> None:
        self.db.delete(row)
