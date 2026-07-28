import uuid
from datetime import datetime, timezone

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
        "slug": "30min",
        "duration_minutes": 30,
        "slot_interval_minutes": 30,
    },
    {
        "title": "60-minute call",
        "slug": "60min",
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
        event_type = EventType(
            user_id=user_id,
            slug=self._next_duration_slug(user_id, payload.duration_minutes),
            **payload.model_dump(),
        )
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
        duration_changed = event_type.duration_minutes != payload.duration_minutes
        if payload.is_default:
            self.repository.clear_default(
                user_id,
                except_event_type_id=event_type.id,
            )
        for key, value in payload.model_dump().items():
            setattr(event_type, key, value)
        if duration_changed:
            event_type.slug = self._next_duration_slug(
                user_id,
                payload.duration_minutes,
                except_event_type_id=event_type.id,
            )
        return self._commit(event_type)

    def create_starter_event_types(self, user_id: uuid.UUID) -> list[EventType]:
        event_types = [
            EventType(user_id=user_id, **values)
            for values in STARTER_EVENT_TYPES
        ]
        return self.repository.add_all(event_types)

    def delete(
        self,
        event_type_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        event_type = self.repository.get_for_user(event_type_id, user_id)
        if not event_type:
            raise AppError(
                status.HTTP_404_NOT_FOUND,
                "event_type_not_found",
                "Event type not found.",
            )
        self.repository.soft_delete(event_type, datetime.now(timezone.utc))
        self._commit(event_type)

    @staticmethod
    def _validate_default(payload: EventTypeInput) -> None:
        if payload.is_default and not payload.is_active:
            raise AppError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "default_event_type_inactive",
                "A default booking must be visible on the public booking page.",
            )

    def _next_duration_slug(
        self,
        user_id: uuid.UUID,
        duration_minutes: int,
        *,
        except_event_type_id: uuid.UUID | None = None,
    ) -> str:
        base_slug = f"{duration_minutes}min"
        slug = base_slug
        suffix = 2
        while self.repository.slug_exists_for_user(
            user_id,
            slug,
            except_event_type_id=except_event_type_id,
        ):
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        return slug

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
