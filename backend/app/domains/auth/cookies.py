from fastapi import Response

from app.core.config import settings
from app.core.security import create_access_token
from app.domains.users.models import User


def set_auth_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=create_access_token(str(user.id), user.token_version),
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        domain=settings.auth_cookie_domain,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )
