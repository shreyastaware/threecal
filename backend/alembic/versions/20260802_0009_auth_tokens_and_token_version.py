"""single-use auth tokens and session revocation version

Revision ID: 20260802_0009
Revises: 20260802_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260802_0009"
down_revision: str | None = "20260802_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    # Incremented on password change/reset so older access tokens stop working.
    if "token_version" not in {column["name"] for column in inspector.get_columns("users")}:
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("token_version", sa.Integer(), server_default="0", nullable=False))

    # AUTO_CREATE_TABLES may already have created this table on a development database.
    if "auth_tokens" in inspector.get_table_names():
        return

    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "purpose",
            sa.Enum("EMAIL_VERIFICATION", "PASSWORD_RESET", name="authtokenpurpose", native_enum=False, length=40),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_auth_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_tokens"),
    )
    op.create_index("ix_auth_tokens_user_id", "auth_tokens", ["user_id"])
    op.create_index("ix_auth_tokens_token_hash", "auth_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_auth_tokens_token_hash", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_user_id", table_name="auth_tokens")
    op.drop_table("auth_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("token_version")
