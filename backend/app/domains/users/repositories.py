import uuid

from sqlalchemy import ColumnElement, Table, delete, inspect, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base
from app.domains.users.models import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username.lower()))

    def create(self, *, email: str, full_name: str, password_hash: str) -> User:
        user = User(email=email, full_name=full_name, password_hash=password_hash)
        self.db.add(user)
        self.db.flush()
        return user

    def update(self, user: User, values: dict[str, object]) -> User:
        for key, value in values.items():
            setattr(user, key, value)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise
        self.db.refresh(user)
        return user

    def delete_with_dependents(self, user: User) -> None:
        """Delete the user and every row that depends on it, children first.

        SQLite does not enforce ON DELETE CASCADE unless the foreign_keys pragma is on,
        so dependents are removed explicitly by walking the mapped foreign keys. This is
        a no-op duplicate of the database cascade on engines that do enforce it.
        """
        existing_tables = set(inspect(self.db.connection()).get_table_names())
        users_table = User.__table__
        assert isinstance(users_table, Table)
        self.db.expunge(user)
        self._delete_cascade(users_table, users_table.c.id == user.id, existing_tables)

    def _delete_cascade(
        self,
        table: Table,
        condition: ColumnElement[bool],
        existing_tables: set[str],
    ) -> None:
        for child in Base.metadata.sorted_tables:
            if child is table or child.name not in existing_tables:
                continue
            for foreign_key in child.foreign_keys:
                if foreign_key.column.table is not table:
                    continue
                child_condition = foreign_key.parent.in_(select(foreign_key.column).where(condition))
                if (foreign_key.ondelete or "").upper() == "SET NULL":
                    self.db.execute(update(child).where(child_condition).values({foreign_key.parent.name: None}))
                else:
                    self._delete_cascade(child, child_condition, existing_tables)
        self.db.execute(delete(table).where(condition))
