from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.domains.auth.schemas import LoginRequest, RegisterRequest
from app.domains.event_types.service import EventTypeService
from app.domains.users.models import User
from app.domains.users.repositories import UserRepository


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.event_types = EventTypeService(db)

    def register(self, data: RegisterRequest) -> User:
        email = data.email.lower()
        if self.users.get_by_email(email):
            raise AppError(
                status.HTTP_409_CONFLICT,
                "email_already_registered",
                "An account with this email already exists.",
            )

        try:
            user = self.users.create(
                email=email,
                full_name=data.full_name,
                password_hash=hash_password(data.password),
            )
            self.event_types.create_starter_event_types(user.id)
            self.db.commit()
            self.db.refresh(user)
            return user
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                status.HTTP_409_CONFLICT,
                "email_already_registered",
                "An account with this email already exists.",
            ) from exc

    def authenticate(self, data: LoginRequest) -> User:
        user = self.users.get_by_email(data.email.lower())
        if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
            raise AppError(
                status.HTTP_401_UNAUTHORIZED,
                "invalid_credentials",
                "Email or password is incorrect.",
            )
        if not user.is_active:
            raise AppError(
                status.HTTP_403_FORBIDDEN,
                "inactive_account",
                "This account has been disabled.",
            )
        return user
