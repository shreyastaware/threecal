from datetime import date
from zoneinfo import ZoneInfoNotFoundError

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.domains.availability.schemas import SlotRead
from app.domains.availability.service import AvailabilityService
from app.domains.bookings.models import Booking
from app.domains.bookings.schemas import BookingCreate, BookingRead
from app.domains.bookings.service import BookingService
from app.domains.email.service import EmailService, get_email_provider
from app.domains.event_types.models import EventType
from app.domains.event_types.schemas import EventTypeRead
from app.domains.users.models import User
from app.domains.users.schemas import PublicUserRead


router = APIRouter(prefix="/public", tags=["public booking"])


def resolve_page(db: Session, username: str, event_slug: str) -> tuple[User, EventType]:
    user = db.scalar(select(User).where(User.username == username.lower(), User.is_active.is_(True)))
    event = db.scalar(select(EventType).where(EventType.user_id == user.id, EventType.slug == event_slug, EventType.is_active.is_(True))) if user else None
    if not user or not event:
        raise AppError(status.HTTP_404_NOT_FOUND, "booking_page_not_found", "Booking page not found.")
    return user, event


@router.get("/{username}/{event_slug}")
def get_booking_page(username: str, event_slug: str, db: Session = Depends(get_db)) -> dict[str, PublicUserRead | EventTypeRead]:
    user, event = resolve_page(db, username, event_slug)
    return {"host": PublicUserRead.model_validate(user), "event_type": EventTypeRead.model_validate(event)}


@router.get("/{username}/{event_slug}/slots", response_model=list[SlotRead])
def get_slots(username: str, event_slug: str, start: date, end: date, timezone: str = Query(default="UTC"), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    user, event = resolve_page(db, username, event_slug)
    if (end - start).days > 31 or end < start:
        raise AppError(422, "invalid_date_range", "Choose a date range of up to 31 days.")
    try:
        return AvailabilityService(db).slots(user, event, start, end, timezone)  # type: ignore[return-value]
    except ZoneInfoNotFoundError as exc:
        raise AppError(422, "invalid_timezone", "Unknown timezone.") from exc


@router.post("/{username}/{event_slug}/bookings", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking(username: str, event_slug: str, payload: BookingCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> Booking:
    user, event = resolve_page(db, username, event_slug)
    booking = BookingService(db).create(user, event, payload)
    background_tasks.add_task(EmailService(get_email_provider()).send_booking_confirmation, booking, event, user)
    return booking
