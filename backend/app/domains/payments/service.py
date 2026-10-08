import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.events import BOOKING_CONFIRMED, DomainEvent, event_bus
from app.domains.bookings.models import Booking, BookingStatus
from app.domains.bookings.repository import is_payment_window_open
from app.domains.event_types.models import EventType
from app.domains.payments.commission import split_payment
from app.domains.payments.gateways import (
    Address,
    HostPayoutProfile,
    OrderRequest,
    OrderTransfer,
    PaymentGateway,
    PayoutRequirement,
    ProviderAPIError,
    get_payment_gateway,
)
from app.domains.payments.models import PaymentAccount
from app.domains.payments.repository import PaymentAccountRepository
from app.domains.payments.schemas import (
    CheckoutPrefill,
    CheckoutRead,
    PaymentAccountCreate,
    PaymentAccountRead,
    PaymentAccountUpdate,
    PaymentVerificationRead,
    PaymentVerificationRequest,
    PayoutRequirementRead,
)
from app.domains.users.models import User


# Route transfers are only supported for INR orders.
ROUTE_CURRENCY = "INR"


def require_gateway() -> PaymentGateway:
    gateway = get_payment_gateway()
    if gateway is None:
        raise AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "payments_not_configured",
            "Online payments are not available yet. Please try again later.",
        )
    return gateway


def provider_error(exc: ProviderAPIError, action: str) -> AppError:
    """Map a provider failure to a user-facing error."""
    if exc.code == "BAD_REQUEST_ERROR":
        return AppError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "payment_provider_rejected",
            f"Razorpay could not {action}: {exc.message}",
        )
    return AppError(
        status.HTTP_502_BAD_GATEWAY,
        "payment_provider_unavailable",
        f"Razorpay could not {action}. {exc.message}",
    )


class PaymentAccountService:
    """Host bank account details and their payout (Route linked account) onboarding."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounts = PaymentAccountRepository(db)

    def get(self, user: User) -> PaymentAccountRead | None:
        account = self.accounts.get_for_user(user.id)
        return self._to_read(account) if account else None

    def create(
        self,
        user: User,
        payload: PaymentAccountCreate,
    ) -> PaymentAccountRead:
        if self.accounts.get_for_user(user.id):
            raise AppError(
                status.HTTP_409_CONFLICT,
                "payment_account_already_exists",
                "A payment account is already connected.",
            )
        try:
            account = self.accounts.create(
                user.id,
                account_number=payload.account_number.get_secret_value(),
                pan=payload.pan.get_secret_value(),
                **self._fields(payload),
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                status.HTTP_409_CONFLICT,
                "payment_account_already_exists",
                "A payment account is already connected.",
            ) from exc
        self.db.refresh(account)
        # Details are saved first so a provider failure can be retried by saving again.
        self._push_to_provider(account)
        return self._to_read(account)

    def update(
        self,
        user: User,
        payload: PaymentAccountUpdate,
    ) -> PaymentAccountRead:
        account = self.accounts.get_for_user(user.id)
        if not account:
            raise AppError(
                status.HTTP_404_NOT_FOUND,
                "payment_account_not_found",
                "Connect a payment account before editing it.",
            )
        if account.linked_account_id and (
            account.account_email != str(payload.account_email) or account.business_type != payload.business_type
        ):
            raise AppError(
                status.HTTP_409_CONFLICT,
                "payment_account_locked_fields",
                "The account email and business type can't be changed after payouts are set up. Contact support to change them.",
            )
        self.accounts.update(
            account,
            account_number=(
                payload.account_number.get_secret_value()
                if payload.account_number
                else None
            ),
            pan=payload.pan.get_secret_value() if payload.pan else None,
            **self._fields(payload),
        )
        self.db.commit()
        self.db.refresh(account)
        self._push_to_provider(account)
        return self._to_read(account)

    def sync(self, user: User) -> PaymentAccountRead:
        """Refresh the activation status, resuming onboarding if it never finished."""
        account = self.accounts.get_for_user(user.id)
        if not account:
            raise AppError(
                status.HTTP_404_NOT_FOUND,
                "payment_account_not_found",
                "Connect a payment account first.",
            )
        gateway = require_gateway()
        current = self.accounts.linked_state(account)
        if not current.linked_account_id or not current.stakeholder_id or not current.product_configuration_id:
            self._push_to_provider(account, gateway)
            return self._to_read(account)
        try:
            state = gateway.fetch_host_status(current)
        except ProviderAPIError as exc:
            raise provider_error(exc, "refresh your payout status") from exc
        self.accounts.apply_linked_state(account, state)
        self.db.commit()
        return self._to_read(account)

    def apply_provider_status(
        self,
        linked_account_id: str,
        activation_status: str,
        requirements: list[PayoutRequirement] | None,
    ) -> bool:
        """Apply an activation status pushed by a provider webhook. Does not commit."""
        account = self.accounts.get_by_linked_account_id(linked_account_id)
        if not account:
            return False
        account.activation_status = activation_status
        self.accounts.set_requirements(account, requirements or [])
        return True

    def _push_to_provider(self, account: PaymentAccount, gateway: PaymentGateway | None = None) -> None:
        gateway = gateway or get_payment_gateway()
        if gateway is None:
            # Payments are not configured on this deployment; details stay saved locally.
            return
        profile = self._profile(account)
        current = self.accounts.linked_state(account)
        try:
            if current.linked_account_id:
                state = gateway.update_host(profile, current)
            else:
                state = gateway.onboard_host(profile, current)
        except ProviderAPIError as exc:
            if exc.partial_state is not None:
                self.accounts.apply_linked_state(account, exc.partial_state)
                self.db.commit()
            raise provider_error(exc, "set up payouts to your bank account") from exc
        self.accounts.apply_linked_state(account, state)
        self.db.commit()

    def _profile(self, account: PaymentAccount) -> HostPayoutProfile:
        pan = self.accounts.pan(account)
        missing = [
            name
            for name, value in {
                "phone": account.phone,
                "business category": account.business_category,
                "business sub-category": account.business_subcategory,
                "address": account.street1,
                "city": account.city,
                "state": account.state,
                "postal code": account.postal_code,
                "PAN": pan,
            }.items()
            if not value
        ]
        if missing:
            raise AppError(
                status.HTTP_409_CONFLICT,
                "payment_account_incomplete",
                f"Add the missing payout details: {', '.join(missing)}.",
            )
        return HostPayoutProfile(
            reference_id=str(account.user_id),
            email=account.account_email,
            phone=str(account.phone),
            contact_name=account.account_name,
            legal_business_name=account.business_name,
            business_type=account.business_type,
            category=str(account.business_category),
            subcategory=str(account.business_subcategory),
            address=Address(
                street1=str(account.street1),
                street2=account.street2,
                city=str(account.city),
                state=str(account.state),
                postal_code=str(account.postal_code),
            ),
            pan=pan,
            account_number=self.accounts.account_number(account),
            ifsc_code=account.branch_ifsc_code,
            beneficiary_name=account.beneficiary_name,
        )

    @staticmethod
    def _fields(payload: PaymentAccountCreate | PaymentAccountUpdate) -> dict[str, Any]:
        return {
            "account_name": payload.account_name,
            "account_email": str(payload.account_email),
            "business_type": payload.business_type,
            "business_name": payload.business_name,
            "branch_ifsc_code": payload.branch_ifsc_code,
            "beneficiary_name": payload.beneficiary_name,
            "phone": payload.phone,
            "business_category": payload.business_category,
            "business_subcategory": payload.business_subcategory,
            "street1": payload.street1,
            "street2": payload.street2,
            "city": payload.city,
            "state": payload.state,
            "postal_code": payload.postal_code,
        }

    def _to_read(self, account: PaymentAccount) -> PaymentAccountRead:
        account_number = self.accounts.account_number(account)
        masked_account_number = (
            account_number[:3] + ("*" * max(0, len(account_number) - 3))
        )
        pan = self.accounts.pan(account)
        return PaymentAccountRead(
            account_name=account.account_name,
            account_email=account.account_email,
            business_type=account.business_type,
            business_name=account.business_name,
            branch_ifsc_code=account.branch_ifsc_code,
            beneficiary_name=account.beneficiary_name,
            masked_account_number=masked_account_number,
            phone=account.phone,
            business_category=account.business_category,
            business_subcategory=account.business_subcategory,
            street1=account.street1,
            street2=account.street2,
            city=account.city,
            state=account.state,
            postal_code=account.postal_code,
            masked_pan=f"{pan[:2]}{'*' * 7}{pan[-1]}" if pan else None,
            activation_status=account.activation_status,  # type: ignore[arg-type]
            payouts_enabled=account.payouts_enabled,
            payouts_configured=get_payment_gateway() is not None,
            requirements=[
                PayoutRequirementRead(
                    field_reference=item.field_reference,
                    reason_code=item.reason_code,
                    status=item.status,
                    description=item.description,
                )
                for item in self.accounts.requirements(account)
            ],
        )


class CheckoutService:
    """Creates platform orders that route the host share to the host's linked account."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounts = PaymentAccountRepository(db)

    def create(self, booking: Booking, event_type: EventType, host: User) -> CheckoutRead:
        if booking.status != BookingStatus.PENDING or booking.booking_amount <= 0:
            raise AppError(409, "booking_not_payable", "This booking does not require a payment.")
        if not is_payment_window_open(booking):
            raise AppError(410, "payment_window_expired", "The booking payment window has expired.")
        gateway = require_gateway()
        currency = event_type.currency.upper()
        if not booking.provider_order_id:
            account = self.accounts.get_for_user(booking.host_id)
            if not account or not account.payouts_enabled or not account.linked_account_id:
                raise AppError(409, "host_payments_not_ready", "This host is not ready to accept paid bookings.")
            if currency != ROUTE_CURRENCY:
                raise AppError(409, "unsupported_currency", "Online payments are only available in INR.")
            split = split_payment(booking.booking_amount, settings.platform_commission_bps)
            notes = {"booking_id": str(booking.id)}
            transfers = (
                [OrderTransfer(account.linked_account_id, split.host_share_minor, currency, notes)]
                if split.host_share_minor > 0
                else []
            )
            try:
                order = gateway.create_order(
                    OrderRequest(
                        amount_minor=booking.booking_amount,
                        currency=currency,
                        receipt=str(booking.id),
                        notes={**notes, "host_id": str(booking.host_id)},
                        transfers=transfers,
                    )
                )
            except ProviderAPIError as exc:
                raise provider_error(exc, "start the payment") from exc
            booking.provider_order_id = order.order_id
            booking.platform_commission_minor = split.platform_commission_minor
            self.db.commit()
        return CheckoutRead(
            provider=gateway.provider,
            booking_id=booking.id,
            key_id=gateway.public_key,
            order_id=str(booking.provider_order_id),
            amount=booking.booking_amount,
            currency=currency,
            name=host.full_name,
            description=event_type.title,
            prefill=CheckoutPrefill(name=booking.invitee_name, email=booking.invitee_email),
        )

    def verify(self, booking: Booking, payload: PaymentVerificationRequest) -> PaymentVerificationRead:
        """Confirm from the Checkout callback so the invitee sees the result immediately.

        The webhook remains the source of truth (and handles refunds for late payments).
        """
        gateway = require_gateway()
        if not booking.provider_order_id or payload.razorpay_order_id != booking.provider_order_id:
            raise AppError(400, "invalid_payment_signature", "The payment does not belong to this booking.")
        if not gateway.verify_checkout_signature(
            payload.razorpay_order_id,
            payload.razorpay_payment_id,
            payload.razorpay_signature,
        ):
            raise AppError(400, "invalid_payment_signature", "The payment signature is invalid.")
        outcome = PaymentConfirmationService(self.db).confirm(
            booking,
            payload.razorpay_payment_id,
            booking.booking_amount,
        )
        if outcome in {PaymentOutcome.SLOT_TAKEN, PaymentOutcome.NOT_PAYABLE}:
            raise AppError(
                409,
                "slot_taken_after_payment",
                "This time was booked by someone else before your payment completed. Your payment will be refunded automatically.",
            )
        return PaymentVerificationRead(booking_id=booking.id, status=booking.status)


class PaymentOutcome(str, enum.Enum):
    CONFIRMED = "confirmed"
    DUPLICATE = "duplicate"
    # The slot was taken while the invitee was paying; the payment must be refunded.
    SLOT_TAKEN = "slot_taken"
    # The booking was cancelled or otherwise closed; the payment must be refunded.
    NOT_PAYABLE = "not_payable"


class PaymentConfirmationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def confirm(self, booking: Booking, payment_id: str, amount_minor: int) -> PaymentOutcome:
        """Mark a booking paid. Commits on success; rolls back on SLOT_TAKEN."""
        if booking.status == BookingStatus.CONFIRMED:
            self.db.commit()
            return PaymentOutcome.DUPLICATE
        # A payment can land just after the window closed; accept it while the slot is still free.
        if booking.status not in {BookingStatus.PENDING, BookingStatus.EXPIRED}:
            return PaymentOutcome.NOT_PAYABLE
        if amount_minor != booking.booking_amount:
            self.db.rollback()
            raise AppError(409, "payment_amount_mismatch", "The provider payment amount does not match the booking amount.")

        # Compare-and-set so the webhook and the Checkout callback racing each other
        # confirm (and announce) the booking exactly once.
        try:
            result = self.db.execute(
                update(Booking)
                .where(Booking.id == booking.id, Booking.status.in_([BookingStatus.PENDING, BookingStatus.EXPIRED]))
                .values(status=BookingStatus.CONFIRMED, provider_payment_id=payment_id)
                .execution_options(synchronize_session=False)
            )
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            return PaymentOutcome.SLOT_TAKEN
        if not result.rowcount:  # type: ignore[attr-defined]
            # Another request changed the booking first.
            self.db.refresh(booking)
            return PaymentOutcome.DUPLICATE if booking.status == BookingStatus.CONFIRMED else PaymentOutcome.NOT_PAYABLE
        booking.status = BookingStatus.CONFIRMED
        booking.provider_payment_id = payment_id
        event_bus.publish(DomainEvent(BOOKING_CONFIRMED, {"booking_id": str(booking.id)}))
        return PaymentOutcome.CONFIRMED


class RefundService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def refund_booking(self, booking: Booking, reason: str) -> None:
        """Fully refund a booking's payment and reverse the host transfer.

        Idempotent: does nothing if a refund already exists or nothing was paid.
        Commits on success; raises AppError if the provider refuses.
        """
        if booking.refund_id:
            return
        if not booking.provider_payment_id or booking.booking_amount <= 0:
            return
        gateway = require_gateway()
        transferred = booking.platform_commission_minor is None or booking.platform_commission_minor < booking.booking_amount
        try:
            refund = gateway.refund(
                booking.provider_payment_id,
                booking.booking_amount,
                reverse_transfers=transferred,
                notes={"booking_id": str(booking.id), "reason": reason[:256]},
            )
        except ProviderAPIError as exc:
            raise AppError(
                status.HTTP_502_BAD_GATEWAY,
                "refund_failed",
                f"Razorpay could not refund this payment. {exc.message}",
            ) from exc
        booking.refund_id = refund.refund_id
        booking.refund_status = refund.status
        booking.refunded_at = datetime.now(timezone.utc)
        self.db.commit()

    @staticmethod
    def apply_refund_status(booking: Booking, refund_status: str) -> None:
        booking.refund_status = refund_status


def get_booking_for_payment(db: Session, booking_id: uuid.UUID) -> tuple[Booking, EventType, User]:
    booking = db.get(Booking, booking_id)
    event_type = db.get(EventType, booking.event_type_id) if booking else None
    host = db.get(User, booking.host_id) if booking else None
    if not booking or not event_type or not host:
        raise AppError(404, "booking_not_found", "Booking not found.")
    return booking, event_type, host
