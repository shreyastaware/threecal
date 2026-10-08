import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BreakInput(BaseModel):
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def ordered(self) -> "BreakInput":
        if self.start_time >= self.end_time:
            raise ValueError("Break end must be after start")
        return self


class WorkingHourInput(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    is_enabled: bool = True
    breaks: list[BreakInput] = []

    @model_validator(mode="after")
    def ordered(self) -> "WorkingHourInput":
        if self.start_time >= self.end_time:
            raise ValueError("End must be after start")
        return self


class ScheduleReplace(BaseModel):
    working_hours: list[WorkingHourInput]


class BreakRead(BreakInput):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class WorkingHourRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    weekday: int
    start_time: time
    end_time: time
    is_enabled: bool
    breaks: list[BreakRead] = []


class ExceptionInput(BaseModel):
    exception_date: date
    is_available: bool = False
    start_time: time | None = None
    end_time: time | None = None
    note: str | None = Field(default=None, max_length=255)


class DateOverrideInput(BaseModel):
    """A one-day override of the weekly schedule.

    ``is_available=False`` blocks the whole day. ``is_available=True`` replaces the
    weekly hours for that date with a single custom range; weekly breaks do not apply.
    """

    is_available: bool = False
    start_time: time | None = None
    end_time: time | None = None
    note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def valid_hours(self) -> "DateOverrideInput":
        if not self.is_available:
            # An unavailable day never carries hours.
            self.start_time = None
            self.end_time = None
            return self
        if self.start_time is None or self.end_time is None:
            raise ValueError("Custom hours need a start and end time")
        if self.start_time >= self.end_time:
            raise ValueError("End must be after start")
        return self


class DateOverrideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    exception_date: date
    is_available: bool
    start_time: time | None
    end_time: time | None
    note: str | None


class SlotRead(BaseModel):
    starts_at: datetime
    ends_at: datetime
