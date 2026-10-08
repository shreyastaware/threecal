"""platform razorpay route payments: linked accounts, orders and refunds

Revision ID: 20260802_0008
Revises: 20260801_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260802_0008"
down_revision: str | None = "20260801_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_STATUSES = sa.text("status IN ('PENDING', 'CONFIRMED')")


def upgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    # Per-host gateway connections were replaced by platform-level Razorpay Route.
    if "doctor_payment_configs" in tables:
        op.drop_table("doctor_payment_configs")

    with op.batch_alter_table("payment_accounts") as batch:
        batch.add_column(sa.Column("phone", sa.String(15), nullable=True))
        batch.add_column(sa.Column("business_category", sa.String(64), nullable=True))
        batch.add_column(sa.Column("business_subcategory", sa.String(64), nullable=True))
        batch.add_column(sa.Column("street1", sa.String(100), nullable=True))
        batch.add_column(sa.Column("street2", sa.String(100), nullable=True))
        batch.add_column(sa.Column("city", sa.String(100), nullable=True))
        batch.add_column(sa.Column("state", sa.String(32), nullable=True))
        batch.add_column(sa.Column("postal_code", sa.String(6), nullable=True))
        batch.add_column(sa.Column("encrypted_pan", sa.Text(), nullable=True))
        batch.add_column(sa.Column("payout_provider", sa.String(32), nullable=False, server_default="razorpay"))
        batch.add_column(sa.Column("linked_account_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("stakeholder_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("product_configuration_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("activation_status", sa.String(32), nullable=False, server_default="not_started"))
        batch.add_column(sa.Column("requirements_json", sa.Text(), nullable=True))
        batch.create_index("ix_payment_accounts_linked_account_id", ["linked_account_id"])

    with op.batch_alter_table("bookings") as batch:
        batch.add_column(sa.Column("provider_order_id", sa.String(255), nullable=True))
        batch.add_column(sa.Column("platform_commission_minor", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("refund_id", sa.String(255), nullable=True))
        batch.add_column(sa.Column("refund_status", sa.String(32), nullable=True))
        batch.add_column(sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_bookings_provider_order_id", ["provider_order_id"])
        batch.create_index("ix_bookings_refund_id", ["refund_id"])


def downgrade() -> None:
    # Batch mode may rebuild the table on SQLite; keep the partial slot index intact.
    op.drop_index("uq_booking_host_start_active", table_name="bookings")
    with op.batch_alter_table("bookings") as batch:
        batch.drop_index("ix_bookings_refund_id")
        batch.drop_index("ix_bookings_provider_order_id")
        batch.drop_column("refunded_at")
        batch.drop_column("refund_status")
        batch.drop_column("refund_id")
        batch.drop_column("platform_commission_minor")
        batch.drop_column("provider_order_id")
    op.create_index(
        "uq_booking_host_start_active",
        "bookings",
        ["host_id", "starts_at"],
        unique=True,
        sqlite_where=ACTIVE_STATUSES,
        postgresql_where=ACTIVE_STATUSES,
    )

    with op.batch_alter_table("payment_accounts") as batch:
        batch.drop_index("ix_payment_accounts_linked_account_id")
        for column in (
            "requirements_json",
            "activation_status",
            "product_configuration_id",
            "stakeholder_id",
            "linked_account_id",
            "payout_provider",
            "encrypted_pan",
            "postal_code",
            "state",
            "city",
            "street2",
            "street1",
            "business_subcategory",
            "business_category",
            "phone",
        ):
            batch.drop_column(column)

    op.create_table(
        "doctor_payment_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("doctor_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Enum("STRIPE", "RAZORPAY", "CASHFREE", "PAYPAL", "BTCPAY", name="paymentprovider"), nullable=False),
        sa.Column("account_id", sa.String(2048), nullable=True),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("encrypted_webhook_secret", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doctor_id", name="uq_doctor_payment_configs_doctor_id"),
    )
    op.create_index("ix_doctor_payment_configs_doctor_id", "doctor_payment_configs", ["doctor_id"])
