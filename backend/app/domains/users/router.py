from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.domains.auth.dependencies import get_current_user
from app.domains.users.models import User
from app.domains.users.repositories import UserRepository
from app.domains.users.schemas import UserProfileUpdate, UserRead


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
        return UserRepository(db).update(current_user, payload.model_dump(exclude_unset=True))
    except IntegrityError as exc:
        raise AppError(status.HTTP_409_CONFLICT, "username_taken", "That booking URL is taken.") from exc
