"""add profiles booking availability and webhooks

Revision ID: 20260720_0002
Revises: 20260720_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260720_0002"
down_revision: str | None = "20260720_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("username", sa.String(50), nullable=True))
        batch.add_column(sa.Column("bio", sa.Text(), nullable=True))
        batch.add_column(sa.Column("timezone", sa.String(64), server_default="UTC", nullable=False))
        batch.add_column(sa.Column("avatar_url", sa.String(2048), nullable=True))
        batch.create_index("ix_users_username", ["username"], unique=True)

    op.create_table(
        "working_hours",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False), sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False), sa.Column("is_enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id", "weekday"),
    )
    op.create_index("ix_working_hours_user_id", "working_hours", ["user_id"])
    op.create_table(
        "availability_breaks", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("working_hour_id", sa.Uuid(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False), sa.Column("end_time", sa.Time(), nullable=False),
        sa.ForeignKeyConstraint(["working_hour_id"], ["working_hours.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_availability_breaks_working_hour_id", "availability_breaks", ["working_hour_id"])
    op.create_table(
        "availability_exceptions", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("exception_date", sa.Date(), nullable=False), sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True), sa.Column("end_time", sa.Time(), nullable=True), sa.Column("note", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id", "exception_date"),
    )
    op.create_index("ix_availability_exceptions_user_id", "availability_exceptions", ["user_id"])
    op.create_index("ix_availability_exceptions_exception_date", "availability_exceptions", ["exception_date"])
    op.create_table(
        "event_types", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False), sa.Column("slug", sa.String(80), nullable=False), sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False), sa.Column("slot_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("price_minor", sa.Integer(), nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id", "slug"),
    )
    op.create_index("ix_event_types_user_id", "event_types", ["user_id"])
    op.create_table(
        "bookings", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("host_id", sa.Uuid(), nullable=False), sa.Column("event_type_id", sa.Uuid(), nullable=False),
        sa.Column("invitee_name", sa.String(120), nullable=False), sa.Column("invitee_email", sa.String(320), nullable=False), sa.Column("invitee_timezone", sa.String(64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True), sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "CONFIRMED", "CANCELLED", "EXPIRED", name="bookingstatus"), nullable=False),
        sa.Column("payment_expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_type_id"], ["event_types.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["host_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("host_id", "starts_at", name="uq_booking_host_start"),
    )
    op.create_index("ix_bookings_host_id", "bookings", ["host_id"])
    op.create_index("ix_bookings_event_type_id", "bookings", ["event_type_id"])
    op.create_index("ix_bookings_invitee_email", "bookings", ["invitee_email"])
    op.create_index("ix_bookings_starts_at", "bookings", ["starts_at"])
    op.create_table(
        "webhook_events", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False), sa.Column("event_type", sa.String(120), nullable=False), sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("provider", "external_id"),
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("bookings")
    op.drop_table("event_types")
    op.drop_table("availability_exceptions")
    op.drop_table("availability_breaks")
    op.drop_table("working_hours")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_username")
        batch.drop_column("avatar_url")
        batch.drop_column("timezone")
        batch.drop_column("bio")
        batch.drop_column("username")
