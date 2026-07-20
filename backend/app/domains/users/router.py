from fastapi import APIRouter, Depends

from app.domains.auth.dependencies import get_current_user
from app.domains.users.models import User
from app.domains.users.schemas import UserRead


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
