import uuid
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_secret, encrypt_secret
from app.core.oauth import OAuthTokens
from app.domains.bookings.models import Booking
from app.domains.bookings.repository import as_utc
from app.domains.calendars.models import BookingCalendarEvent, CalendarConnection, ConnectionStatus, SelectedCalendar


class CalendarConnectionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_user(self, user_id: uuid.UUID) -> list[CalendarConnection]:
        return list(
            self.db.scalars(
                select(CalendarConnection)
                .where(CalendarConnection.user_id == user_id)
                .order_by(CalendarConnection.created_at, CalendarConnection.id)
            )
        )

    def get_for_user(self, connection_id: uuid.UUID, user_id: uuid.UUID) -> CalendarConnection | None:
        return self.db.scalar(
            select(CalendarConnection).where(
                CalendarConnection.id == connection_id,
                CalendarConnection.user_id == user_id,
            )
        )

    def get(self, connection_id: uuid.UUID) -> CalendarConnection | None:
        return self.db.get(CalendarConnection, connection_id)

    def get_by_account(self, user_id: uuid.UUID, provider: str, account_email: str) -> CalendarConnection | None:
        return self.db.scalar(
            select(CalendarConnection).where(
                CalendarConnection.user_id == user_id,
                CalendarConnection.provider == provider,
                CalendarConnection.account_email == account_email,
            )
        )

    def first_active_for_provider(self, user_id: uuid.UUID, provider: str) -> CalendarConnection | None:
        return self.db.scalar(
            select(CalendarConnection)
            .where(
                CalendarConnection.user_id == user_id,
                CalendarConnection.provider == provider,
                CalendarConnection.status == ConnectionStatus.ACTIVE.value,
            )
            .order_by(CalendarConnection.created_at, CalendarConnection.id)
            .limit(1)
        )

    def has_any(self, user_id: uuid.UUID) -> bool:
        return self.db.scalar(select(CalendarConnection.id).where(CalendarConnection.user_id == user_id).limit(1)) is not None

    def add(self, connection: CalendarConnection) -> CalendarConnection:
        self.db.add(connection)
        self.db.flush()
        return connection

    def delete(self, connection: CalendarConnection) -> None:
        # SQLite does not enforce ON DELETE CASCADE here, so remove children explicitly.
        self.db.execute(delete(BookingCalendarEvent).where(BookingCalendarEvent.connection_id == connection.id))
        self.db.execute(delete(SelectedCalendar).where(SelectedCalendar.connection_id == connection.id))
        self.db.delete(connection)

    @staticmethod
    def set_tokens(connection: CalendarConnection, tokens: OAuthTokens) -> None:
        connection.encrypted_access_token = encrypt_secret(tokens.access_token)
        if tokens.refresh_token:
            connection.encrypted_refresh_token = encrypt_secret(tokens.refresh_token)
        connection.token_expires_at = tokens.expires_at
        if tokens.scope:
            connection.scopes = tokens.scope

    @staticmethod
    def tokens(connection: CalendarConnection) -> OAuthTokens:
        return OAuthTokens(
            access_token=decrypt_secret(connection.encrypted_access_token),
            refresh_token=decrypt_secret(connection.encrypted_refresh_token) if connection.encrypted_refresh_token else None,
            expires_at=connection.token_expires_at,
            scope=connection.scopes,
        )


class SelectedCalendarRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_connection(self, connection_id: uuid.UUID) -> list[SelectedCalendar]:
        return list(self.db.scalars(select(SelectedCalendar).where(SelectedCalendar.connection_id == connection_id)))

    def list_for_user(self, user_id: uuid.UUID) -> list[SelectedCalendar]:
        return list(self.db.scalars(select(SelectedCalendar).where(SelectedCalendar.user_id == user_id)))

    def conflict_calendars_for_user(self, user_id: uuid.UUID) -> list[SelectedCalendar]:
        return list(
            self.db.scalars(
                select(SelectedCalendar).where(
                    SelectedCalendar.user_id == user_id,
                    SelectedCalendar.check_conflicts.is_(True),
                )
            )
        )

    def destination_for_user(self, user_id: uuid.UUID) -> SelectedCalendar | None:
        return self.db.scalar(
            select(SelectedCalendar).where(
                SelectedCalendar.user_id == user_id,
                SelectedCalendar.is_destination.is_(True),
            ).limit(1)
        )

    def clear_destination(self, user_id: uuid.UUID) -> None:
        self.db.execute(
            update(SelectedCalendar)
            .where(SelectedCalendar.user_id == user_id, SelectedCalendar.is_destination.is_(True))
            .values(is_destination=False)
            .execution_options(synchronize_session="fetch")
        )

    def replace_for_connection(self, connection: CalendarConnection, rows: list[SelectedCalendar]) -> None:
        self.db.execute(delete(SelectedCalendar).where(SelectedCalendar.connection_id == connection.id))
        self.db.add_all(rows)
        self.db.flush()


class BookingCalendarEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_booking(self, booking_id: uuid.UUID) -> list[BookingCalendarEvent]:
        return list(self.db.scalars(select(BookingCalendarEvent).where(BookingCalendarEvent.booking_id == booking_id)))

    def find(self, booking_id: uuid.UUID, connection_id: uuid.UUID, calendar_id: str) -> BookingCalendarEvent | None:
        return self.db.scalar(
            select(BookingCalendarEvent).where(
                BookingCalendarEvent.booking_id == booking_id,
                BookingCalendarEvent.connection_id == connection_id,
                BookingCalendarEvent.external_calendar_id == calendar_id,
            )
        )

    def find_for_provider(self, booking_id: uuid.UUID, provider: str) -> BookingCalendarEvent | None:
        return self.db.scalar(
            select(BookingCalendarEvent).where(
                BookingCalendarEvent.booking_id == booking_id,
                BookingCalendarEvent.provider == provider,
            ).limit(1)
        )

    def own_events_in_range(
        self,
        connection_ids: list[uuid.UUID],
        start: datetime,
        end: datetime,
    ) -> tuple[set[str], set[tuple[datetime, datetime]]]:
        """External ids and booking times of Threecal-created events overlapping the range."""
        if not connection_ids:
            return set(), set()
        rows = self.db.execute(
            select(BookingCalendarEvent.external_event_id, Booking.starts_at, Booking.ends_at)
            .join(Booking, Booking.id == BookingCalendarEvent.booking_id)
            .where(
                BookingCalendarEvent.connection_id.in_(connection_ids),
                Booking.starts_at < end,
                Booking.ends_at > start,
            )
        ).all()
        return (
            {row.external_event_id for row in rows},
            {(as_utc(row.starts_at), as_utc(row.ends_at)) for row in rows},
        )

    def add(self, event: BookingCalendarEvent) -> BookingCalendarEvent:
        self.db.add(event)
        self.db.flush()
        return event

    def delete(self, event: BookingCalendarEvent) -> None:
        self.db.delete(event)
