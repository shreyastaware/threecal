"""booking management, invitee self-service and reminders

Revision ID: 20260803_0012
Revises: 20260803_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260803_0012"
down_revision: str | None = "20260803_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


BOOKING_COLUMNS: list[sa.Column] = [  # type: ignore[type-arg]
    # SHA-256 of the invitee's manage-booking token.
    sa.Column("manage_token_hash", sa.String(64), nullable=True),
    # iCalendar SEQUENCE, bumped on every reschedule/cancellation.
    sa.Column("sequence", sa.Integer(), server_default="0", nullable=False),
    sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cancelled_by", sa.String(16), nullable=True),
    sa.Column("cancellation_reason", sa.Text(), nullable=True),
]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("bookings")}
    missing = [column for column in BOOKING_COLUMNS if column.name not in existing]
    if missing:
        with op.batch_alter_table("bookings") as batch:
            for column in missing:
                batch.add_column(column)

    # AUTO_CREATE_TABLES may already have created this table on a development database.
    if "booking_reminders" in inspector.get_table_names():
        return
    op.create_table(
        "booking_reminders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("offset_minutes", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name="fk_booking_reminders_booking_id_bookings",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_booking_reminders"),
        sa.UniqueConstraint("booking_id", "offset_minutes", name="uq_booking_reminders_booking_id"),
    )
    op.create_index("ix_booking_reminders_booking_id", "booking_reminders", ["booking_id"])


def downgrade() -> None:
    op.drop_index("ix_booking_reminders_booking_id", table_name="booking_reminders")
    op.drop_table("booking_reminders")
    with op.batch_alter_table("bookings") as batch:
        for column in reversed(BOOKING_COLUMNS):
            batch.drop_column(column.name)
