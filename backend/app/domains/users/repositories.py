import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
