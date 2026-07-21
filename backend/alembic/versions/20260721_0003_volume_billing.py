"""add provider credentials and volume billing

Revision ID: 20260721_0003
Revises: 6f276d9c2831
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260721_0003"
down_revision: str | None = "6f276d9c2831"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
    op.create_table(
        "platform_billing",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("doctor_id", sa.Uuid(), nullable=False),
        sa.Column("dodopayments_customer_id", sa.String(255), nullable=True),
        sa.Column("payment_method_id", sa.String(255), nullable=True),
        sa.Column("dodopayments_subscription_id", sa.String(255), nullable=True),
        sa.Column("current_cycle_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_cycle_earnings", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doctor_id", name="uq_platform_billing_doctor_id"),
    )
    op.create_index("ix_platform_billing_doctor_id", "platform_billing", ["doctor_id"])
    op.create_table(
        "billing_invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("doctor_id", sa.Uuid(), nullable=False),
        sa.Column("cycle_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cycle_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("earnings_minor", sa.Integer(), nullable=False),
        sa.Column("fee_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("provider_payment_id", sa.String(255), nullable=True),
        sa.Column("status", sa.Enum("PROCESSING", "PAID", "FAILED", name="invoicestatus"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doctor_id", "cycle_start", name="uq_billing_invoice_doctor_cycle"),
    )
    op.create_index("ix_billing_invoices_doctor_id", "billing_invoices", ["doctor_id"])
    with op.batch_alter_table("bookings") as batch:
        batch.add_column(sa.Column("provider_payment_id", sa.String(255), nullable=True))
        batch.add_column(sa.Column("booking_amount", sa.Integer(), server_default="0", nullable=False))
        batch.create_index("ix_bookings_provider_payment_id", ["provider_payment_id"])


def downgrade() -> None:
    with op.batch_alter_table("bookings") as batch:
        batch.drop_index("ix_bookings_provider_payment_id")
        batch.drop_column("booking_amount")
        batch.drop_column("provider_payment_id")
    op.drop_table("billing_invoices")
    op.drop_table("platform_billing")
    op.drop_table("doctor_payment_configs")
