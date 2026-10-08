from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.domains.auth.cookies import clear_auth_cookie, set_auth_cookie
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.schemas import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.domains.auth.service import AuthService
from app.domains.email.service import EmailService, get_email_provider
from app.domains.users.models import User
from app.domains.users.schemas import UserRead


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("register", limit=10, window_seconds=3600))],
)
def register(
    data: RegisterRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> AuthResponse:
    service = AuthService(db)
    user = service.register(data)
    link = service.create_email_verification_link(user)
    background_tasks.add_task(EmailService(get_email_provider()).send_email_verification, user, link)
    set_auth_cookie(response, user)
    return AuthResponse(user=UserRead.model_validate(user))


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit("login", limit=10, window_seconds=60, key_by_email=True))],
)
def login(
    data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    user = AuthService(db).authenticate(data)
    set_auth_cookie(response, user)
    return AuthResponse(user=UserRead.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    clear_auth_cookie(response)


@router.post(
    "/verify-email",
    response_model=UserRead,
    dependencies=[Depends(rate_limit("verify-email", limit=10, window_seconds=900))],
)
def verify_email(data: VerifyEmailRequest, db: Session = Depends(get_db)) -> User:
    return AuthService(db).verify_email(data.token)


@router.post(
    "/resend-verification",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("resend-verification", limit=3, window_seconds=900))],
)
def resend_verification(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    link = AuthService(db).resend_email_verification(current_user)
    background_tasks.add_task(EmailService(get_email_provider()).send_email_verification, current_user, link)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("forgot-password", limit=5, window_seconds=900, key_by_email=True))],
)
def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> None:
    # Always 202 so the response never reveals whether an account exists.
    issued = AuthService(db).create_password_reset_link(data.email)
    if issued:
        user, link = issued
        background_tasks.add_task(EmailService(get_email_provider()).send_password_reset, user, link)


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("reset-password", limit=10, window_seconds=900))],
)
def reset_password(
    data: ResetPasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    AuthService(db).reset_password(data)
    # Every existing session (including this browser's) was revoked; ask for a fresh sign-in.
    clear_auth_cookie(response)
