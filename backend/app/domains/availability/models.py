import uuid
from datetime import date, time

from sqlalchemy import Boolean, ForeignKey, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WorkingHour(Base):
    __tablename__ = "working_hours"
    __table_args__ = (UniqueConstraint("user_id", "weekday"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class AvailabilityBreak(Base):
    __tablename__ = "availability_breaks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    working_hour_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("working_hours.id", ondelete="CASCADE"), index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class AvailabilityException(Base):
    __tablename__ = "availability_exceptions"
    __table_args__ = (UniqueConstraint("user_id", "exception_date"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exception_date: Mapped[date] = mapped_column(index=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
