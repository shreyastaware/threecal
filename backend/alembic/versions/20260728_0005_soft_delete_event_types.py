"""soft delete event types

Revision ID: 20260728_0005
Revises: 20260728_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260728_0005"
down_revision: str | None = "20260728_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("event_types") as batch:
        batch.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("event_types") as batch:
        batch.drop_column("deleted_at")
