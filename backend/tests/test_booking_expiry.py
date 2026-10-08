import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.domains.availability.models import WorkingHour
from app.domains.availability.service import AvailabilityService
from app.domains.bookings.models import Booking, BookingStatus
from app.domains.bookings.service import BookingExpiryService
from app.domains.event_types.models import EventType
from app.domains.users.models import User


@pytest.fixture
def db(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'expiry.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session
    engine.dispose()


def _setup(db: Session) -> tuple[User, EventType, datetime]:
    host = User(email="host@example.com", full_name="Host", password_hash="x", username="host", timezone="UTC")
    db.add(host)
    db.flush()
    event = EventType(user_id=host.id, title="Call", slug="30min", duration_minutes=30, slot_interval_minutes=30, price_minor=50000, currency="INR")
    day = (datetime.now(timezone.utc) + timedelta(days=2)).date()
    db.add_all([event, WorkingHour(user_id=host.id, weekday=day.weekday(), start_time=datetime(2000, 1, 1, 9).time(), end_time=datetime(2000, 1, 1, 10).time(), is_enabled=True)])
    db.commit()
    return host, event, datetime.combine(day, datetime(2000, 1, 1, 9).time(), timezone.utc)


def _booking(host: User, event: EventType, starts_at: datetime, status: BookingStatus, expires_in: timedelta) -> Booking:
    return Booking(
        id=uuid.uuid4(), host_id=host.id, event_type_id=event.id, invitee_name="Invitee", invitee_email="i@example.com",
        invitee_timezone="UTC", starts_at=starts_at, ends_at=starts_at + timedelta(minutes=30), status=status,
        booking_amount=50000, payment_expires_at=datetime.now(timezone.utc) + expires_in,
    )


def test_unpaid_booking_releases_slot_after_payment_window(db: Session) -> None:
    host, event, starts_at = _setup(db)
    db.add(_booking(host, event, starts_at, BookingStatus.PENDING, timedelta(minutes=-1)))
    db.commit()

    slots = AvailabilityService(db).slots(host, event, starts_at.date(), starts_at.date(), "UTC")
    assert starts_at in {slot["starts_at"] for slot in slots}

    assert BookingExpiryService(db).expire_stale() == 1
    assert db.scalar(select(Booking.status)) == BookingStatus.EXPIRED
    db.add(_booking(host, event, starts_at, BookingStatus.PENDING, timedelta(minutes=10)))
    db.commit()


def test_open_payment_window_still_holds_slot(db: Session) -> None:
    host, event, starts_at = _setup(db)
    db.add(_booking(host, event, starts_at, BookingStatus.PENDING, timedelta(minutes=5)))
    db.commit()

    slots = AvailabilityService(db).slots(host, event, starts_at.date(), starts_at.date(), "UTC")
    assert starts_at not in {slot["starts_at"] for slot in slots}
    db.add(_booking(host, event, starts_at, BookingStatus.PENDING, timedelta(minutes=10)))
    with pytest.raises(IntegrityError):
        db.commit()
