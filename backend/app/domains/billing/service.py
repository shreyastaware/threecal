from datetime import datetime, timezone

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.billing.dodo import DodoPaymentsClient, DodoPaymentsError
from app.domains.billing.models import BillingInvoice, InvoiceStatus, PlatformBilling
from app.domains.billing.repository import BillingRepository, cycle_end
from app.domains.billing.schemas import BillingRunRead, BillingSetupComplete, BillingSetupRead
from app.domains.users.models import User


def calculate_platform_fee(earnings_minor: int) -> int:
    if earnings_minor <= 500_000:
        return 0
    if earnings_minor <= 5_000_000:
        return 20_000
    if earnings_minor <= 15_000_000:
        return 100_000
    if earnings_minor <= 30_000_000:
        return 300_000
    return (earnings_minor * 3 + 50) // 100


class PlatformBillingService:
    def __init__(self, db: Session, client: DodoPaymentsClient | None = None) -> None:
        self.db = db
        self.repository = BillingRepository(db)
        self.client = client or DodoPaymentsClient()

    def start_setup(self, doctor: User) -> BillingSetupRead:
        billing = self.repository.get_or_create(doctor.id)
        try:
            if not billing.dodopayments_customer_id:
                billing.dodopayments_customer_id = self.client.create_customer(doctor.full_name, doctor.email, str(doctor.id))
            checkout_url = self.client.create_mandate_checkout(billing.dodopayments_customer_id, str(doctor.id))
        except DodoPaymentsError as exc:
            self.db.rollback()
            raise AppError(status.HTTP_502_BAD_GATEWAY, "billing_setup_failed", str(exc)) from exc
        self.db.commit()
        return BillingSetupRead(checkout_url=checkout_url, customer_id=billing.dodopayments_customer_id)

    def complete_setup(self, doctor: User, payload: BillingSetupComplete) -> PlatformBilling:
        billing = self.repository.get_for_doctor(doctor.id)
        if not billing or not billing.dodopayments_customer_id:
            raise AppError(409, "billing_setup_not_started", "Start billing setup first.")
        try:
            verified = self.client.payment_method_belongs_to_customer(billing.dodopayments_customer_id, payload.payment_method_id)
            subscription_verified = self.client.subscription_belongs_to_customer(billing.dodopayments_customer_id, payload.subscription_id)
        except DodoPaymentsError as exc:
            raise AppError(502, "billing_verification_failed", str(exc)) from exc
        if not verified or not subscription_verified:
            raise AppError(422, "invalid_billing_mandate", "The recurring payment mandate does not belong to this customer.")
        billing.payment_method_id = payload.payment_method_id
        billing.dodopayments_subscription_id = payload.subscription_id
        self.db.commit()
        self.db.refresh(billing)
        return billing


class BillingCycleService:
    def __init__(self, db: Session, client: DodoPaymentsClient | None = None) -> None:
        self.db = db
        self.repository = BillingRepository(db)
        self.client = client or DodoPaymentsClient()

    def run(self, now: datetime | None = None) -> BillingRunRead:
        current_time = now or datetime.now(timezone.utc)
        processed = pending = failed = 0
        for billing in self.repository.due(current_time):
            try:
                outcome = self._process_one(billing)
                processed += outcome == "processed"
                pending += outcome == "pending"
                failed += outcome == "failed"
            except DodoPaymentsError:
                self.db.rollback()
                failed += 1
        return BillingRunRead(processed=processed, pending=pending, failed=failed)

    def _process_one(self, billing: PlatformBilling) -> str:
        end = cycle_end(billing.current_cycle_start)
        invoice = self.repository.invoice_for_cycle(billing.doctor_id, billing.current_cycle_start)
        fee = calculate_platform_fee(billing.current_cycle_earnings)
        if not invoice:
            invoice = BillingInvoice(
                doctor_id=billing.doctor_id,
                cycle_start=billing.current_cycle_start,
                cycle_end=end,
                earnings_minor=billing.current_cycle_earnings,
                fee_minor=fee,
                status=InvoiceStatus.PROCESSING if fee else InvoiceStatus.PAID,
            )
            self.db.add(invoice)
            self.db.flush()
            if fee:
                if not billing.payment_method_id or not billing.dodopayments_subscription_id:
                    invoice.status = InvoiceStatus.FAILED
                    self.db.commit()
                    return "failed"
                invoice.provider_payment_id = self.client.charge_subscription(billing.dodopayments_subscription_id, fee, str(invoice.id))
                self.db.commit()
                return "pending"
            self._advance_cycle(billing, end)
            self.db.commit()
            return "processed"

        if invoice.status == InvoiceStatus.PAID:
            self._advance_cycle(billing, end)
            self.db.commit()
            return "processed"
        if invoice.status == InvoiceStatus.FAILED or not invoice.provider_payment_id:
            return "failed"
        payment_status = self.client.payment_status(invoice.provider_payment_id)
        if payment_status == "succeeded":
            invoice.status = InvoiceStatus.PAID
            self._advance_cycle(billing, end)
            self.db.commit()
            return "processed"
        if payment_status in {"failed", "cancelled"}:
            invoice.status = InvoiceStatus.FAILED
            self.db.commit()
            return "failed"
        return "pending"

    @staticmethod
    def _advance_cycle(billing: PlatformBilling, end: datetime) -> None:
        billing.current_cycle_earnings = 0
        billing.current_cycle_start = end
