import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.domains.auth.dependencies import get_current_user
from app.domains.event_types.models import EventType
from app.domains.event_types.schemas import EventTypeInput, EventTypeRead
from app.domains.users.models import User


router = APIRouter(prefix="/event-types", tags=["event types"])


@router.get("", response_model=list[EventTypeRead])
def list_event_types(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[EventType]:
    return list(db.scalars(select(EventType).where(EventType.user_id == current_user.id)))


@router.post("", response_model=EventTypeRead, status_code=status.HTTP_201_CREATED)
def create_event_type(payload: EventTypeInput, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EventType:
    event_type = EventType(user_id=current_user.id, **payload.model_dump())
    db.add(event_type)
    db.commit()
    db.refresh(event_type)
    return event_type


@router.patch("/{event_type_id}", response_model=EventTypeRead)
def update_event_type(event_type_id: uuid.UUID, payload: EventTypeInput, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EventType:
    event_type = db.scalar(select(EventType).where(EventType.id == event_type_id, EventType.user_id == current_user.id))
    if not event_type:
        raise AppError(status.HTTP_404_NOT_FOUND, "event_type_not_found", "Event type not found.")
    for key, value in payload.model_dump().items():
        setattr(event_type, key, value)
    db.commit()
    db.refresh(event_type)
    return event_type
