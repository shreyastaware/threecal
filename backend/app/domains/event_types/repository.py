import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domains.event_types.models import EventType


class EventTypeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_user(self, user_id: uuid.UUID) -> list[EventType]:
        return list(
            self.db.scalars(
                select(EventType)
                .where(EventType.user_id == user_id)
                .order_by(EventType.created_at, EventType.id)
            )
        )

    def list_active_for_user(self, user_id: uuid.UUID) -> list[EventType]:
        return list(
            self.db.scalars(
                select(EventType)
                .where(
                    EventType.user_id == user_id,
                    EventType.is_active.is_(True),
                )
                .order_by(EventType.created_at, EventType.id)
            )
        )

    def get_for_user(
        self,
        event_type_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> EventType | None:
        return self.db.scalar(
            select(EventType).where(
                EventType.id == event_type_id,
                EventType.user_id == user_id,
            )
        )

    def get_active_by_slug(
        self,
        user_id: uuid.UUID,
        slug: str,
    ) -> EventType | None:
        return self.db.scalar(
            select(EventType).where(
                EventType.user_id == user_id,
                EventType.slug == slug,
                EventType.is_active.is_(True),
            )
        )

    def get_default_for_user(
        self,
        user_id: uuid.UUID,
        *,
        active_only: bool = False,
    ) -> EventType | None:
        statement = select(EventType).where(
            EventType.user_id == user_id,
            EventType.is_default.is_(True),
        )
        if active_only:
            statement = statement.where(EventType.is_active.is_(True))
        return self.db.scalar(statement)

    def add(self, event_type: EventType) -> EventType:
        self.db.add(event_type)
        return event_type

    def add_all(self, event_types: list[EventType]) -> list[EventType]:
        self.db.add_all(event_types)
        return event_types

    def clear_default(
        self,
        user_id: uuid.UUID,
        *,
        except_event_type_id: uuid.UUID | None = None,
    ) -> None:
        statement = (
            update(EventType)
            .where(
                EventType.user_id == user_id,
                EventType.is_default.is_(True),
            )
            .values(is_default=False)
        )
        if except_event_type_id:
            statement = statement.where(EventType.id != except_event_type_id)
        self.db.execute(statement.execution_options(synchronize_session="fetch"))
