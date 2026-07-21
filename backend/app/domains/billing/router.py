import hmac

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.domains.auth.dependencies import get_current_user
from app.domains.billing.repository import BillingRepository
from app.domains.billing.schemas import BillingRunRead, BillingSetupComplete, BillingSetupRead, PlatformBillingRead
from app.domains.billing.service import BillingCycleService, PlatformBillingService
from app.domains.users.models import User


router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/me", response_model=PlatformBillingRead)
def get_billing(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PlatformBillingRead:
    billing = BillingRepository(db).get_or_create(current_user.id)
    db.commit()
    return PlatformBillingRead.model_validate(billing)


@router.post("/setup", response_model=BillingSetupRead)
def start_setup(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> BillingSetupRead:
    return PlatformBillingService(db).start_setup(current_user)


@router.post("/setup/complete", response_model=PlatformBillingRead)
def complete_setup(payload: BillingSetupComplete, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PlatformBillingRead:
    billing = PlatformBillingService(db).complete_setup(current_user, payload)
    return PlatformBillingRead.model_validate(billing)


@router.post("/run-cycle", response_model=BillingRunRead)
def run_cycle(x_cron_secret: str = Header(), db: Session = Depends(get_db)) -> BillingRunRead:
    if not hmac.compare_digest(x_cron_secret, settings.billing_cron_secret):
        raise AppError(401, "invalid_cron_secret", "Invalid cron secret.")
    return BillingCycleService(db).run()
