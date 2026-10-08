import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.conferencing.schemas import AuthorizationUrlRead, ConferencingConnectionRead
from app.domains.conferencing.service import ConferencingConnectionService
from app.domains.users.models import User


router = APIRouter(prefix="/conferencing", tags=["conferencing"])


@router.get("/connections", response_model=list[ConferencingConnectionRead])
def list_connections(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ConferencingConnectionRead]:
    return ConferencingConnectionService(db).list_connections(current_user)


@router.get("/oauth/{provider}/authorize", response_model=AuthorizationUrlRead)
def authorize(provider: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AuthorizationUrlRead:
    return ConferencingConnectionService(db).authorization_url(current_user, provider)


@router.get("/oauth/{provider}/callback", include_in_schema=False)
def oauth_callback(
    provider: str,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    # The signed state identifies the host, so no session cookie is needed on this cross-site redirect.
    url = ConferencingConnectionService(db).complete_oauth(provider, code=code, state=state, error=error)
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(connection_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    ConferencingConnectionService(db).delete_connection(current_user, connection_id)
