import logging
import uuid

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.domains.bookings.repository import BookingRepository
from app.domains.users.avatar import AvatarImageProcessor
from app.domains.users.models import User
from app.domains.users.repositories import UserRepository
from app.domains.users.storage import ObjectStorage, ObjectStorageError


logger = logging.getLogger(__name__)
PROFILE_PICTURES_PREFIX = "profile-pictures"


class UserProfileService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def update(self, user: User, values: dict[str, object]) -> User:
        return self.repository.update(user, values)


class UserAvatarService:
    def __init__(
        self,
        repository: UserRepository,
        storage: ObjectStorage,
        processor: AvatarImageProcessor | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.processor = processor or AvatarImageProcessor()

    def upload(
        self,
        user: User,
        *,
        content: bytes,
        declared_content_type: str | None,
    ) -> User:
        processed = self.processor.process(content, declared_content_type)
        object_key = (
            f"{PROFILE_PICTURES_PREFIX}/{user.id}/"
            f"{uuid.uuid4().hex}.{processed.extension}"
        )
        previous_avatar_url = user.avatar_url
        public_url = self.storage.upload(
            object_key,
            processed.content,
            processed.content_type,
        )

        try:
            updated_user = self.repository.update(user, {"avatar_url": public_url})
        except Exception:
            self._delete_quietly(object_key)
            raise

        if previous_avatar_url and previous_avatar_url != public_url:
            previous_key = self.storage.key_from_public_url(previous_avatar_url)
            if previous_key:
                self._delete_quietly(previous_key)
        return updated_user

    def _delete_quietly(self, key: str) -> None:
        try:
            self.storage.delete(key)
        except ObjectStorageError:
            logger.exception("Unable to delete profile image object %s", key)


class UserAccountService:
    """Credential changes and account deletion for the signed-in user."""

    def __init__(self, db: Session, storage: ObjectStorage) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.bookings = BookingRepository(db)
        self.storage = storage

    def change_password(self, user: User, current_password: str, new_password: str) -> User:
        self._require_password(user, current_password, "Your current password is incorrect.")
        user.password_hash = hash_password(new_password)
        # Revokes every other session; the caller re-issues this session's cookie.
        user.token_version += 1
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User, password: str) -> None:
        self._require_password(user, password, "That password is incorrect.")
        if self.bookings.count_upcoming_confirmed_for_host(user.id):
            raise AppError(
                status.HTTP_409_CONFLICT,
                "upcoming_bookings",
                "You have upcoming confirmed bookings. Cancel them first, then delete your account.",
            )

        self._disconnect_integrations(user)
        avatar_url = user.avatar_url
        self.users.delete_with_dependents(user)
        self.db.commit()

        if avatar_url:
            # Best effort: a leftover image must not undo a completed account deletion.
            key = self.storage.key_from_public_url(avatar_url)
            if key:
                try:
                    self.storage.delete(key)
                except ObjectStorageError:
                    logger.exception("Unable to delete profile image object %s", key)

    def _disconnect_integrations(self, user: User) -> None:
        """Revoke calendar and conferencing tokens at the providers before the rows are deleted."""
        # Imported here to keep the users domain free of integration imports at module load.
        from app.domains.calendars.repository import CalendarConnectionRepository
        from app.domains.calendars.service import CalendarConnectionService
        from app.domains.conferencing.repository import ConferencingConnectionRepository
        from app.domains.conferencing.service import ConferencingConnectionService

        for calendar in CalendarConnectionRepository(self.db).list_for_user(user.id):
            CalendarConnectionService(self.db).delete_connection(user, calendar.id)
        for conferencing in ConferencingConnectionRepository(self.db).list_for_user(user.id):
            ConferencingConnectionService(self.db).delete_connection(user, conferencing.id)

    @staticmethod
    def _require_password(user: User, password: str, message: str) -> None:
        if not user.password_hash or not verify_password(password, user.password_hash):
            raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_password", message)
