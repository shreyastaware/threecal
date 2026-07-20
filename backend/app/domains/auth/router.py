from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.domains.auth.schemas import AuthResponse, LoginRequest, RegisterRequest
from app.domains.auth.service import AuthService
from app.domains.users.models import User


router = APIRouter(prefix="/auth", tags=["auth"])


def set_auth_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=create_access_token(str(user.id)),
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        path="/",
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    data: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    user = AuthService(db).register(data)
    set_auth_cookie(response, user)
    return AuthResponse(user=user)


@router.post("/login", response_model=AuthResponse)
def login(
    data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    user = AuthService(db).authenticate(data)
    set_auth_cookie(response, user)
    return AuthResponse(user=user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        domain=settings.auth_cookie_domain,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )
