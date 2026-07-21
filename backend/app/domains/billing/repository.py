import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.billing.models import BillingInvoice, PlatformBilling


class BillingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_doctor(self, doctor_id: uuid.UUID) -> PlatformBilling | None:
        return self.db.scalar(select(PlatformBilling).where(PlatformBilling.doctor_id == doctor_id))

    def get_or_create(self, doctor_id: uuid.UUID) -> PlatformBilling:
        billing = self.get_for_doctor(doctor_id)
        if not billing:
            billing = PlatformBilling(doctor_id=doctor_id)
            self.db.add(billing)
            self.db.flush()
        return billing

    def due(self, now: datetime) -> list[PlatformBilling]:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        records = list(self.db.scalars(select(PlatformBilling)))
        return [record for record in records if cycle_end(record.current_cycle_start) <= now]

    def invoice_for_cycle(self, doctor_id: uuid.UUID, cycle_start: datetime) -> BillingInvoice | None:
        return self.db.scalar(
            select(BillingInvoice).where(BillingInvoice.doctor_id == doctor_id, BillingInvoice.cycle_start == cycle_start)
        )


def cycle_end(start: datetime) -> datetime:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    year = start.year + (1 if start.month == 12 else 0)
    month = 1 if start.month == 12 else start.month + 1
    return start.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
