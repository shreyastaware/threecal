"""add default event types

Revision ID: 20260728_0004
Revises: 20260721_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260728_0004"
down_revision: str | None = "20260721_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("event_types") as batch:
        batch.add_column(
            sa.Column(
                "is_default",
                sa.Boolean(),
                server_default="0",
                nullable=False,
            )
        )
    op.create_index(
        "uq_event_types_default_per_user",
        "event_types",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("is_default = 1"),
        postgresql_where=sa.text("is_default"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_event_types_default_per_user",
        table_name="event_types",
    )
    with op.batch_alter_table("event_types") as batch:
        batch.drop_column("is_default")
