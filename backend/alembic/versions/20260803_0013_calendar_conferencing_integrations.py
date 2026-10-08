"""calendar + conferencing integrations and event type locations

Revision ID: 20260803_0013
Revises: 20260803_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260803_0013"
down_revision: str | None = "20260803_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    event_type_columns = {column["name"] for column in inspector.get_columns("event_types")}
    with op.batch_alter_table("event_types") as batch:
        if "location_type" not in event_type_columns:
            batch.add_column(sa.Column("location_type", sa.String(32), server_default="none", nullable=False))
        if "location_value" not in event_type_columns:
            batch.add_column(sa.Column("location_value", sa.String(2048), nullable=True))

    # AUTO_CREATE_TABLES may already have created these tables on a development database.
    if "calendar_connections" not in tables:
        op.create_table(
            "calendar_connections",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("provider", sa.String(32), nullable=False),
            sa.Column("account_email", sa.String(320), nullable=False),
            sa.Column("encrypted_access_token", sa.Text(), nullable=False),
            sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
            sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("scopes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), server_default="active", nullable=False),
            *_timestamps(),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_calendar_connections_user_id_users", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", name="pk_calendar_connections"),
            sa.UniqueConstraint("user_id", "provider", "account_email", name="uq_calendar_connections_user_provider_email"),
        )
        op.create_index("ix_calendar_connections_user_id", "calendar_connections", ["user_id"])

    if "selected_calendars" not in tables:
        op.create_table(
            "selected_calendars",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("connection_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("external_calendar_id", sa.String(1024), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("check_conflicts", sa.Boolean(), server_default="0", nullable=False),
            sa.Column("is_destination", sa.Boolean(), server_default="0", nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(
                ["connection_id"], ["calendar_connections.id"], name="fk_selected_calendars_connection_id_calendar_connections", ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_selected_calendars_user_id_users", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", name="pk_selected_calendars"),
            sa.UniqueConstraint("connection_id", "external_calendar_id", name="uq_selected_calendars_connection_calendar"),
        )
        op.create_index("ix_selected_calendars_connection_id", "selected_calendars", ["connection_id"])
        op.create_index("ix_selected_calendars_user_id", "selected_calendars", ["user_id"])

    if "booking_calendar_events" not in tables:
        op.create_table(
            "booking_calendar_events",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("booking_id", sa.Uuid(), nullable=False),
            sa.Column("connection_id", sa.Uuid(), nullable=False),
            sa.Column("provider", sa.String(32), nullable=False),
            sa.Column("external_calendar_id", sa.String(1024), nullable=False),
            sa.Column("external_event_id", sa.String(1024), nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], name="fk_booking_calendar_events_booking_id_bookings", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["connection_id"],
                ["calendar_connections.id"],
                name="fk_booking_calendar_events_connection_id_calendar_connections",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_booking_calendar_events"),
            sa.UniqueConstraint("booking_id", "connection_id", "external_calendar_id", name="uq_booking_calendar_events_booking_calendar"),
        )
        op.create_index("ix_booking_calendar_events_booking_id", "booking_calendar_events", ["booking_id"])
        op.create_index("ix_booking_calendar_events_connection_id", "booking_calendar_events", ["connection_id"])

    if "conferencing_connections" not in tables:
        op.create_table(
            "conferencing_connections",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("provider", sa.String(32), nullable=False),
            sa.Column("account_email", sa.String(320), nullable=False),
            sa.Column("encrypted_access_token", sa.Text(), nullable=False),
            sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
            sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("scopes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), server_default="active", nullable=False),
            *_timestamps(),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_conferencing_connections_user_id_users", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", name="pk_conferencing_connections"),
            sa.UniqueConstraint("user_id", "provider", name="uq_conferencing_connections_user_provider"),
        )
        op.create_index("ix_conferencing_connections_user_id", "conferencing_connections", ["user_id"])

    if "booking_meetings" not in tables:
        op.create_table(
            "booking_meetings",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("booking_id", sa.Uuid(), nullable=False),
            sa.Column("connection_id", sa.Uuid(), nullable=False),
            sa.Column("provider", sa.String(32), nullable=False),
            sa.Column("external_meeting_id", sa.String(255), nullable=False),
            sa.Column("join_url", sa.String(2048), nullable=False),
            *_timestamps(),
            sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], name="fk_booking_meetings_booking_id_bookings", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["connection_id"],
                ["conferencing_connections.id"],
                name="fk_booking_meetings_connection_id_conferencing_connections",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_booking_meetings"),
            sa.UniqueConstraint("booking_id", name="uq_booking_meetings_booking_id"),
        )
        op.create_index("ix_booking_meetings_booking_id", "booking_meetings", ["booking_id"])
        op.create_index("ix_booking_meetings_connection_id", "booking_meetings", ["connection_id"])


def downgrade() -> None:
    op.drop_table("booking_meetings")
    op.drop_table("conferencing_connections")
    op.drop_table("booking_calendar_events")
    op.drop_table("selected_calendars")
    op.drop_table("calendar_connections")
    with op.batch_alter_table("event_types") as batch:
        batch.drop_column("location_value")
        batch.drop_column("location_type")
