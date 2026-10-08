from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.domains.auth.cookies import clear_auth_cookie, set_auth_cookie
from app.domains.auth.dependencies import get_current_user
from app.domains.users.avatar import MAX_AVATAR_BYTES, AvatarValidationError
from app.domains.users.models import User
from app.domains.users.repositories import UserRepository
from app.domains.users.schemas import (
    AccountDeleteRequest,
    PasswordChangeRequest,
    UserProfileUpdate,
    UserRead,
)
from app.domains.users.service import UserAccountService, UserAvatarService, UserProfileService
from app.domains.users.storage import (
    ObjectStorage,
    ObjectStorageConfigurationError,
    ObjectStorageError,
    get_object_storage,
)


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
def update_current_user(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    try:
        return UserProfileService(UserRepository(db)).update(
            current_user,
            payload.model_dump(exclude_unset=True),
        )
    except IntegrityError as exc:
        raise AppError(status.HTTP_409_CONFLICT, "username_taken", "That booking URL is taken.") from exc


@router.post("/me/password", response_model=UserRead)
def change_current_user_password(
    payload: PasswordChangeRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_object_storage),
) -> User:
    user = UserAccountService(db, storage).change_password(
        current_user,
        payload.current_password,
        payload.new_password,
    )
    # Other sessions are revoked by the version bump; keep this one signed in.
    set_auth_cookie(response, user)
    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_user(
    payload: AccountDeleteRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_object_storage),
) -> None:
    UserAccountService(db, storage).delete(current_user, payload.password)
    clear_auth_cookie(response)


@router.post("/me/avatar", response_model=UserRead)
def upload_current_user_avatar(
    avatar: Annotated[UploadFile, File()],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_object_storage),
) -> User:
    content = avatar.file.read(MAX_AVATAR_BYTES + 1)
    try:
        return UserAvatarService(UserRepository(db), storage).upload(
            current_user,
            content=content,
            declared_content_type=avatar.content_type,
        )
    except AvatarValidationError as exc:
        error_status = (
            status.HTTP_413_CONTENT_TOO_LARGE
            if exc.code == "avatar_too_large"
            else status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            if exc.code in {"avatar_type_unsupported", "avatar_type_mismatch"}
            else status.HTTP_400_BAD_REQUEST
        )
        raise AppError(error_status, exc.code, exc.message) from exc
    except ObjectStorageConfigurationError as exc:
        raise AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "avatar_storage_unavailable",
            "Profile image storage is not configured.",
        ) from exc
    except ObjectStorageError as exc:
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            "avatar_upload_failed",
            "The profile image could not be stored. Please try again.",
        ) from exc
