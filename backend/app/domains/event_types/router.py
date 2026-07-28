import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.event_types.models import EventType
from app.domains.event_types.schemas import EventTypeInput, EventTypeRead
from app.domains.event_types.service import EventTypeService
from app.domains.users.models import User


router = APIRouter(prefix="/event-types", tags=["event types"])


@router.get("", response_model=list[EventTypeRead])
def list_event_types(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[EventType]:
    return EventTypeService(db).list_for_user(current_user.id)


@router.post("", response_model=EventTypeRead, status_code=status.HTTP_201_CREATED)
def create_event_type(payload: EventTypeInput, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EventType:
    return EventTypeService(db).create(current_user.id, payload)


@router.patch("/{event_type_id}", response_model=EventTypeRead)
def update_event_type(event_type_id: uuid.UUID, payload: EventTypeInput, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EventType:
    return EventTypeService(db).update(event_type_id, current_user.id, payload)


@router.delete("/{event_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event_type(event_type_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    EventTypeService(db).delete(event_type_id, current_user.id)
