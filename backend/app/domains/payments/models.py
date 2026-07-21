import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PaymentProvider(str, enum.Enum):
    STRIPE = "stripe"
    RAZORPAY = "razorpay"
    CASHFREE = "cashfree"
    PAYPAL = "paypal"
    BTCPAY = "btcpay"


class DoctorPaymentConfig(Base):
    __tablename__ = "doctor_payment_configs"
    __table_args__ = (UniqueConstraint("doctor_id", name="uq_doctor_payment_configs_doctor_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    doctor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[PaymentProvider] = mapped_column(Enum(PaymentProvider))
    account_id: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    encrypted_api_key: Mapped[str] = mapped_column(Text)
    encrypted_webhook_secret: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
