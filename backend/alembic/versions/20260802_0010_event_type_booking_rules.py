"""add booking rules to event types

Revision ID: 20260802_0010
Revises: 20260802_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260802_0010"
down_revision: str | None = "20260802_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("event_types") as batch:
        batch.add_column(sa.Column("buffer_before_minutes", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("buffer_after_minutes", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("minimum_notice_minutes", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("max_days_in_advance", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("daily_booking_limit", sa.Integer(), nullable=True))
    # Existing event types get the default 60-day booking window; NULL means unlimited.
    op.execute(sa.text("UPDATE event_types SET max_days_in_advance = 60"))


def downgrade() -> None:
    with op.batch_alter_table("event_types") as batch:
        batch.drop_column("daily_booking_limit")
        batch.drop_column("max_days_in_advance")
        batch.drop_column("minimum_notice_minutes")
        batch.drop_column("buffer_after_minutes")
        batch.drop_column("buffer_before_minutes")
