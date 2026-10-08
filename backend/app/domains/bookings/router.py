import uuid
from datetime import date
from zoneinfo import ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.rate_limit import rate_limit
from app.domains.auth.dependencies import get_current_user
from app.domains.availability.schemas import SlotRead
from app.domains.availability.service import AvailabilityService
from app.domains.bookings.models import Booking
from app.domains.bookings.repository import BookingScope
from app.domains.bookings.schemas import (
    BookingCancelRequest,
    BookingCreate,
    BookingRead,
    BookingRescheduleRequest,
    HostBookingPage,
    HostBookingRead,
    InviteeBookingRead,
    InviteeCancelRequest,
    InviteeRescheduleRequest,
    PublicEventTypeRead,
    PublicProfileRead,
)
from app.domains.bookings.service import (
    DEFAULT_PAGE_SIZE,
    BookingLifecycleService,
    BookingService,
    HostBookingService,
    InviteeBookingService,
    PublicBookingService,
)
from app.domains.event_types.models import EventType
from app.domains.users.models import User
from app.domains.users.schemas import PublicUserRead


router = APIRouter(prefix="/public", tags=["public booking"])
# Authenticated host booking management.
host_router = APIRouter(prefix="/bookings", tags=["bookings"])
# Token-authenticated invitee self-service. Include before ``router`` so
# ``/public/bookings/...`` is not captured by ``/public/{username}/{event_slug}``.
invitee_router = APIRouter(prefix="/public/bookings", tags=["invitee bookings"])


def resolve_page(db: Session, username: str, event_slug: str) -> tuple[User, EventType]:
    return PublicBookingService(db).resolve_page(username, event_slug)


@router.get("/{username}", response_model=PublicProfileRead)
def get_public_profile(
    username: str,
    db: Session = Depends(get_db),
) -> PublicProfileRead:
    user, events, default_event = PublicBookingService(db).get_profile(username)
    return PublicProfileRead(
        host=PublicUserRead.model_validate(user),
        event_types=[PublicEventTypeRead.model_validate(event) for event in events],
        default_event_type_slug=default_event.slug if default_event else None,
    )


@router.get("/{username}/{event_slug}")
def get_booking_page(username: str, event_slug: str, db: Session = Depends(get_db)) -> dict[str, PublicUserRead | PublicEventTypeRead]:
    user, event = resolve_page(db, username, event_slug)
    return {"host": PublicUserRead.model_validate(user), "event_type": PublicEventTypeRead.model_validate(event)}


@router.get("/{username}/{event_slug}/slots", response_model=list[SlotRead])
def get_slots(username: str, event_slug: str, start: date, end: date, timezone: str = Query(default="UTC"), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    user, event = resolve_page(db, username, event_slug)
    if (end - start).days > 31 or end < start:
        raise AppError(422, "invalid_date_range", "Choose a date range of up to 31 days.")
    try:
        return AvailabilityService(db).slots(user, event, start, end, timezone)  # type: ignore[return-value]
    except ZoneInfoNotFoundError as exc:
        raise AppError(422, "invalid_timezone", "Unknown timezone.") from exc


@router.post(
    "/{username}/{event_slug}/bookings",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("public-booking", limit=10, window_seconds=600))],
)
def create_booking(username: str, event_slug: str, payload: BookingCreate, db: Session = Depends(get_db)) -> Booking:
    user, event = resolve_page(db, username, event_slug)
    # Confirmation emails are sent by the booking.confirmed subscribers (notifications domain).
    return BookingService(db).create(user, event, payload)


# Host booking management --------------------------------------------------------


@host_router.get("", response_model=HostBookingPage)
def list_bookings(
    scope: BookingScope = Query(default=BookingScope.UPCOMING),
    event_type_id: uuid.UUID | None = None,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HostBookingPage:
    return HostBookingService(db).list(current_user, scope, event_type_id=event_type_id, limit=limit, offset=offset)


@host_router.get("/{booking_id}", response_model=HostBookingRead)
def get_booking(booking_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> HostBookingRead:
    service = HostBookingService(db)
    return service.to_read(service.get(current_user, booking_id))


@host_router.post("/{booking_id}/cancel", response_model=HostBookingRead)
def cancel_booking(
    booking_id: uuid.UUID,
    payload: BookingCancelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HostBookingRead:
    # Host cancellations fully refund a captured payment.
    return HostBookingService(db).cancel(current_user, booking_id, payload.reason)


@host_router.post("/{booking_id}/reschedule", response_model=HostBookingRead)
def reschedule_booking(
    booking_id: uuid.UUID,
    payload: BookingRescheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HostBookingRead:
    return HostBookingService(db).reschedule(current_user, booking_id, payload.starts_at)


@host_router.get("/{booking_id}/slots", response_model=list[SlotRead])
def get_reschedule_slots(
    booking_id: uuid.UUID,
    start: date,
    end: date,
    timezone: str = Query(default="UTC"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    booking = HostBookingService(db).get(current_user, booking_id)
    return BookingLifecycleService(db).reschedule_slots(booking, start, end, timezone)  # type: ignore[return-value]


# Invitee self-service -------------------------------------------------------------


@invitee_router.get(
    "/{booking_id}",
    response_model=InviteeBookingRead,
    dependencies=[Depends(rate_limit("invitee-booking-read", limit=60, window_seconds=600))],
)
def get_invitee_booking(booking_id: uuid.UUID, token: str = Query(min_length=1, max_length=256), db: Session = Depends(get_db)) -> InviteeBookingRead:
    service = InviteeBookingService(db)
    return service.to_read(service.get(booking_id, token))


@invitee_router.get(
    "/{booking_id}/slots",
    response_model=list[SlotRead],
    dependencies=[Depends(rate_limit("invitee-booking-read", limit=60, window_seconds=600))],
)
def get_invitee_reschedule_slots(
    booking_id: uuid.UUID,
    start: date,
    end: date,
    token: str = Query(min_length=1, max_length=256),
    timezone: str = Query(default="UTC"),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return InviteeBookingService(db).slots(booking_id, token, start, end, timezone)  # type: ignore[return-value]


@invitee_router.post(
    "/{booking_id}/cancel",
    response_model=InviteeBookingRead,
    dependencies=[Depends(rate_limit("invitee-booking-change", limit=10, window_seconds=600))],
)
def cancel_invitee_booking(booking_id: uuid.UUID, payload: InviteeCancelRequest, db: Session = Depends(get_db)) -> InviteeBookingRead:
    return InviteeBookingService(db).cancel(booking_id, payload.token, payload.reason)


@invitee_router.post(
    "/{booking_id}/reschedule",
    response_model=InviteeBookingRead,
    dependencies=[Depends(rate_limit("invitee-booking-change", limit=10, window_seconds=600))],
)
def reschedule_invitee_booking(booking_id: uuid.UUID, payload: InviteeRescheduleRequest, db: Session = Depends(get_db)) -> InviteeBookingRead:
    return InviteeBookingService(db).reschedule(booking_id, payload.token, payload.starts_at)
