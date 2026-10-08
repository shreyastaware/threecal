import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PaymentProvider(str, enum.Enum):
    RAZORPAY = "razorpay"


class LinkedAccountStatus(str, enum.Enum):
    """Activation status of the host's payout (Route) product configuration."""

    NOT_STARTED = "not_started"
    REQUESTED = "requested"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNDER_REVIEW = "under_review"
    ACTIVATED = "activated"
    SUSPENDED = "suspended"


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
    # Extra KYC details required by the payout provider (Razorpay Route).
    phone: Mapped[str | None] = mapped_column(String(15), nullable=True)
    business_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    business_subcategory: Mapped[str | None] = mapped_column(String(64), nullable=True)
    street1: Mapped[str | None] = mapped_column(String(100), nullable=True)
    street2: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    encrypted_pan: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Payout provider (linked account) state.
    payout_provider: Mapped[str] = mapped_column(
        String(32),
        default=PaymentProvider.RAZORPAY.value,
        server_default=PaymentProvider.RAZORPAY.value,
    )
    linked_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stakeholder_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product_configuration_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    activation_status: Mapped[str] = mapped_column(
        String(32),
        default=LinkedAccountStatus.NOT_STARTED.value,
        server_default=LinkedAccountStatus.NOT_STARTED.value,
    )
    # JSON list of outstanding provider requirements, shown to the host.
    requirements_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @property
    def payouts_enabled(self) -> bool:
        """Paid bookings need an activated linked account to route the host share to."""
        return bool(self.linked_account_id) and self.activation_status == LinkedAccountStatus.ACTIVATED.value
