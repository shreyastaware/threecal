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


class BusinessType(str, enum.Enum):
    LLP = "llp"
    NGO = "ngo"
    OTHER = "other"
    INDIVIDUAL = "individual"
    PARTNERSHIP = "partnership"
    PROPRIETORSHIP = "proprietorship"
    PUBLIC_LIMITED = "public_limited"
    PRIVATE_LIMITED = "private_limited"
    TRUST = "trust"
    SOCIETY = "society"
    NOT_YET_REGISTERED = "not_yet_registered"
    EDUCATIONAL_INSTITUTES = "educational_institutes"


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


class PaymentAccount(Base):
    __tablename__ = "payment_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_payment_accounts_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    account_name: Mapped[str] = mapped_column(String(120))
    account_email: Mapped[str] = mapped_column(String(320))
    business_type: Mapped[BusinessType] = mapped_column(Enum(BusinessType))
    business_name: Mapped[str] = mapped_column(String(160))
    branch_ifsc_code: Mapped[str] = mapped_column(String(11))
    encrypted_account_number: Mapped[str] = mapped_column(Text)
    beneficiary_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
