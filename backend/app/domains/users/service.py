import logging
import uuid

from app.domains.users.avatar import AvatarImageProcessor
from app.domains.users.models import User
from app.domains.users.repositories import UserRepository
from app.domains.users.storage import ObjectStorage, ObjectStorageError


logger = logging.getLogger(__name__)


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
            f"profile-images/{user.id}/{uuid.uuid4().hex}.{processed.extension}"
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
