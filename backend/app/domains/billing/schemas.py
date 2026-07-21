from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BillingSetupRead(BaseModel):
    checkout_url: str
    customer_id: str


class BillingSetupComplete(BaseModel):
    payment_method_id: str
    subscription_id: str


class PlatformBillingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dodopayments_customer_id: str | None
    payment_method_id: str | None
    current_cycle_start: datetime
    current_cycle_earnings: int
    ready: bool


class BillingRunRead(BaseModel):
    processed: int
    pending: int
    failed: int
