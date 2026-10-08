import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domains.auth.models import AuthToken, AuthTokenPurpose


class AuthTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: uuid.UUID,
        purpose: AuthTokenPurpose,
        token_hash: str,
        expires_at: datetime,
    ) -> AuthToken:
        token = AuthToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(token)
        self.db.flush()
        return token

    def get_by_hash(self, token_hash: str, purpose: AuthTokenPurpose) -> AuthToken | None:
        return self.db.scalar(
            select(AuthToken).where(
                AuthToken.token_hash == token_hash,
                AuthToken.purpose == purpose,
            )
        )

    def invalidate_unused(self, user_id: uuid.UUID, purpose: AuthTokenPurpose, used_at: datetime) -> None:
        self.db.execute(
            update(AuthToken)
            .where(
                AuthToken.user_id == user_id,
                AuthToken.purpose == purpose,
                AuthToken.used_at.is_(None),
            )
            .values(used_at=used_at)
            .execution_options(synchronize_session=False)
        )
