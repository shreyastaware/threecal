"""add payment accounts

Revision ID: 20260729_0006
Revises: 20260728_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260729_0006"
down_revision: str | None = "20260728_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "payment_accounts" in inspector.get_table_names():
        return

    op.create_table(
        "payment_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_name", sa.String(120), nullable=False),
        sa.Column("account_email", sa.String(320), nullable=False),
        sa.Column(
            "business_type",
            sa.Enum(
                "LLP",
                "NGO",
                "OTHER",
                "INDIVIDUAL",
                "PARTNERSHIP",
                "PROPRIETORSHIP",
                "PUBLIC_LIMITED",
                "PRIVATE_LIMITED",
                "TRUST",
                "SOCIETY",
                "NOT_YET_REGISTERED",
                "EDUCATIONAL_INSTITUTES",
                name="businesstype",
            ),
            nullable=False,
        ),
        sa.Column("business_name", sa.String(160), nullable=False),
        sa.Column("branch_ifsc_code", sa.String(11), nullable=False),
        sa.Column("encrypted_account_number", sa.Text(), nullable=False),
        sa.Column("beneficiary_name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_payment_accounts_user_id"),
    )
    op.create_index(
        "ix_payment_accounts_user_id",
        "payment_accounts",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("payment_accounts")
