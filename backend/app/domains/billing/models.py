import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InvoiceStatus(str, enum.Enum):
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"


class PlatformBilling(Base):
    __tablename__ = "platform_billing"
    __table_args__ = (UniqueConstraint("doctor_id", name="uq_platform_billing_doctor_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    dodopayments_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_method_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dodopayments_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_cycle_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # All monetary values are integer minor units to avoid rounding errors.
    current_cycle_earnings: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    @property
    def ready(self) -> bool:
        return bool(self.dodopayments_customer_id and self.payment_method_id and self.dodopayments_subscription_id)


class BillingInvoice(Base):
    __tablename__ = "billing_invoices"
    __table_args__ = (UniqueConstraint("doctor_id", "cycle_start", name="uq_billing_invoice_doctor_cycle"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    cycle_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cycle_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    earnings_minor: Mapped[int] = mapped_column(Integer)
    fee_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.PAID)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
