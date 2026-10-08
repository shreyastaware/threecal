from urllib.parse import urlencode

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.domains.auth.models import AuthTokenPurpose
from app.domains.auth.schemas import LoginRequest, RegisterRequest, ResetPasswordRequest
from app.domains.auth.tokens import AuthTokenService
from app.domains.event_types.service import EventTypeService
from app.domains.users.models import User
from app.domains.users.repositories import UserRepository


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.event_types = EventTypeService(db)
        self.tokens = AuthTokenService(db)

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

    def create_email_verification_link(self, user: User) -> str:
        raw_token = self.tokens.issue(user.id, AuthTokenPurpose.EMAIL_VERIFICATION)
        self.db.commit()
        return frontend_link("/verify-email", raw_token)

    def resend_email_verification(self, user: User) -> str:
        if user.is_email_verified:
            raise AppError(
                status.HTTP_409_CONFLICT,
                "email_already_verified",
                "Your email address is already verified.",
            )
        return self.create_email_verification_link(user)

    def verify_email(self, raw_token: str) -> User:
        user = self._user_for_token(raw_token, AuthTokenPurpose.EMAIL_VERIFICATION)
        user.is_email_verified = True
        self.db.commit()
        self.db.refresh(user)
        return user

    def create_password_reset_link(self, email: str) -> tuple[User, str] | None:
        """Return the user and reset link, or None when no usable account exists.

        Callers must respond identically either way so accounts cannot be enumerated.
        """
        user = self.users.get_by_email(email.lower())
        if not user or not user.is_active:
            return None
        raw_token = self.tokens.issue(user.id, AuthTokenPurpose.PASSWORD_RESET)
        self.db.commit()
        return user, frontend_link("/reset-password", raw_token)

    def reset_password(self, data: ResetPasswordRequest) -> User:
        user = self._user_for_token(data.token, AuthTokenPurpose.PASSWORD_RESET)
        user.password_hash = hash_password(data.new_password)
        user.token_version += 1
        # Receiving the reset email proves ownership of the address.
        user.is_email_verified = True
        self.db.commit()
        self.db.refresh(user)
        return user

    def _user_for_token(self, raw_token: str, purpose: AuthTokenPurpose) -> User:
        user_id = self.tokens.consume(raw_token, purpose)
        user = self.users.get_by_id(user_id)
        if not user or not user.is_active:
            self.db.rollback()
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                "invalid_token",
                "This link is invalid or has expired. Please request a new one.",
            )
        return user


def frontend_link(path: str, raw_token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}{path}?{urlencode({'token': raw_token})}"
