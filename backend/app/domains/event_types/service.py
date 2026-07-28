import uuid

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.event_types.models import EventType
from app.domains.event_types.repository import EventTypeRepository
from app.domains.event_types.schemas import EventTypeInput


STARTER_EVENT_TYPES: tuple[dict[str, object], ...] = (
    {
        "title": "30-minute call",
        "slug": "30-minute-call",
        "duration_minutes": 30,
        "slot_interval_minutes": 30,
    },
    {
        "title": "60-minute call",
        "slug": "60-minute-call",
        "duration_minutes": 60,
        "slot_interval_minutes": 60,
    },
)


class EventTypeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = EventTypeRepository(db)

    def list_for_user(self, user_id: uuid.UUID) -> list[EventType]:
        return self.repository.list_for_user(user_id)

    def create(self, user_id: uuid.UUID, payload: EventTypeInput) -> EventType:
        self._validate_default(payload)
        event_type = EventType(user_id=user_id, **payload.model_dump())
        if event_type.is_default:
            self.repository.clear_default(user_id)
        self.repository.add(event_type)
        return self._commit(event_type)

    def update(
        self,
        event_type_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: EventTypeInput,
    ) -> EventType:
        event_type = self.repository.get_for_user(event_type_id, user_id)
        if not event_type:
            raise AppError(
                status.HTTP_404_NOT_FOUND,
                "event_type_not_found",
                "Event type not found.",
            )

        self._validate_default(payload)
        if payload.is_default:
            self.repository.clear_default(
                user_id,
                except_event_type_id=event_type.id,
            )
        for key, value in payload.model_dump().items():
            setattr(event_type, key, value)
        return self._commit(event_type)

    def create_starter_event_types(self, user_id: uuid.UUID) -> list[EventType]:
        event_types = [
            EventType(user_id=user_id, **values)
            for values in STARTER_EVENT_TYPES
        ]
        return self.repository.add_all(event_types)

    @staticmethod
    def _validate_default(payload: EventTypeInput) -> None:
        if payload.is_default and not payload.is_active:
            raise AppError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "default_event_type_inactive",
                "A default booking must be visible on the public booking page.",
            )

    def _commit(self, event_type: EventType) -> EventType:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                status.HTTP_409_CONFLICT,
                "event_type_conflict",
                "An event type with this booking URL already exists.",
            ) from exc
        self.db.refresh(event_type)
        return event_type
