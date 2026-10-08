import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_secret, encrypt_secret
from app.core.oauth import OAuthTokens
from app.domains.conferencing.models import BookingMeeting, ConferencingConnection


class ConferencingConnectionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_user(self, user_id: uuid.UUID) -> list[ConferencingConnection]:
        return list(
            self.db.scalars(
                select(ConferencingConnection)
                .where(ConferencingConnection.user_id == user_id)
                .order_by(ConferencingConnection.created_at, ConferencingConnection.id)
            )
        )

    def get_for_user(self, connection_id: uuid.UUID, user_id: uuid.UUID) -> ConferencingConnection | None:
        return self.db.scalar(
            select(ConferencingConnection).where(
                ConferencingConnection.id == connection_id,
                ConferencingConnection.user_id == user_id,
            )
        )

    def get(self, connection_id: uuid.UUID) -> ConferencingConnection | None:
        return self.db.get(ConferencingConnection, connection_id)

    def get_for_provider(self, user_id: uuid.UUID, provider: str) -> ConferencingConnection | None:
        return self.db.scalar(
            select(ConferencingConnection).where(
                ConferencingConnection.user_id == user_id,
                ConferencingConnection.provider == provider,
            )
        )

    def add(self, connection: ConferencingConnection) -> ConferencingConnection:
        self.db.add(connection)
        self.db.flush()
        return connection

    def delete(self, connection: ConferencingConnection) -> None:
        # SQLite does not enforce ON DELETE CASCADE here, so remove children explicitly.
        self.db.execute(delete(BookingMeeting).where(BookingMeeting.connection_id == connection.id))
        self.db.delete(connection)

    @staticmethod
    def set_tokens(connection: ConferencingConnection, tokens: OAuthTokens) -> None:
        connection.encrypted_access_token = encrypt_secret(tokens.access_token)
        if tokens.refresh_token:
            connection.encrypted_refresh_token = encrypt_secret(tokens.refresh_token)
        connection.token_expires_at = tokens.expires_at
        if tokens.scope:
            connection.scopes = tokens.scope

    @staticmethod
    def tokens(connection: ConferencingConnection) -> OAuthTokens:
        return OAuthTokens(
            access_token=decrypt_secret(connection.encrypted_access_token),
            refresh_token=decrypt_secret(connection.encrypted_refresh_token) if connection.encrypted_refresh_token else None,
            expires_at=connection.token_expires_at,
            scope=connection.scopes,
        )


class BookingMeetingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_booking(self, booking_id: uuid.UUID) -> BookingMeeting | None:
        return self.db.scalar(select(BookingMeeting).where(BookingMeeting.booking_id == booking_id))

    def add(self, meeting: BookingMeeting) -> BookingMeeting:
        self.db.add(meeting)
        self.db.flush()
        return meeting

    def delete(self, meeting: BookingMeeting) -> None:
        self.db.delete(meeting)
