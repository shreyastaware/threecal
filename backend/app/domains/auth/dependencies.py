import uuid

from fastapi import Depends, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import decode_access_token_claims
from app.domains.users.models import User
from app.domains.users.repositories import UserRepository


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.auth_cookie_name)
    claims = decode_access_token_claims(token) if token else None
    try:
        user_id = uuid.UUID(claims.subject) if claims else None
    except ValueError:
        user_id = None

    user = UserRepository(db).get_by_id(user_id) if user_id else None
    # A token minted before the latest password change/reset is no longer valid.
    if not user or not user.is_active or not claims or claims.token_version != user.token_version:
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            "not_authenticated",
            "Authentication is required.",
        )
    return user
