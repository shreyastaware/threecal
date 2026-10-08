"""drop platform billing and release slots held by inactive bookings

Revision ID: 20260801_0007
Revises: 20260729_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260801_0007"
down_revision: str | None = "20260729_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_STATUSES = sa.text("status IN ('PENDING', 'CONFIRMED')")


def upgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    # Usage-based platform billing was removed; the platform now earns through Razorpay Route commission.
    if "billing_invoices" in tables:
        op.drop_table("billing_invoices")
    if "platform_billing" in tables:
        op.drop_table("platform_billing")

    with op.batch_alter_table("bookings") as batch:
        batch.drop_constraint("uq_booking_host_start", type_="unique")
    op.create_index(
        "uq_booking_host_start_active",
        "bookings",
        ["host_id", "starts_at"],
        unique=True,
        sqlite_where=ACTIVE_STATUSES,
        postgresql_where=ACTIVE_STATUSES,
    )


def downgrade() -> None:
    op.drop_index("uq_booking_host_start_active", table_name="bookings")
    with op.batch_alter_table("bookings") as batch:
        batch.create_unique_constraint("uq_booking_host_start", ["host_id", "starts_at"])

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
