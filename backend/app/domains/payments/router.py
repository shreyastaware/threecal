import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.domains.auth.dependencies import get_current_user
from app.domains.bookings.models import Booking
from app.domains.event_types.models import EventType
from app.domains.payments.models import DoctorPaymentConfig, PaymentProvider
from app.domains.payments.repository import PaymentConfigRepository
from app.domains.payments.schemas import (
    CheckoutRead,
    CredentialConnectRequest,
    OAuthStartRead,
    PaymentAccountCreate,
    PaymentAccountRead,
    PaymentAccountUpdate,
    PaymentConfigRead,
)
from app.domains.payments.service import (
    CheckoutService,
    PaymentAccountService,
    PaymentOnboardingService,
)
from app.domains.users.models import User


router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/config", response_model=PaymentConfigRead | None)
def get_config(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DoctorPaymentConfig | None:
    return PaymentConfigRepository(db).get_for_doctor(current_user.id)


@router.get("/account", response_model=PaymentAccountRead | None)
def get_payment_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentAccountRead | None:
    return PaymentAccountService(db).get(current_user)


@router.post(
    "/account",
    response_model=PaymentAccountRead,
    status_code=201,
)
def create_payment_account(
    payload: PaymentAccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentAccountRead:
    return PaymentAccountService(db).create(current_user, payload)


@router.patch("/account", response_model=PaymentAccountRead)
def update_payment_account(
    payload: PaymentAccountUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentAccountRead:
    return PaymentAccountService(db).update(current_user, payload)


@router.post("/config", response_model=PaymentConfigRead)
def connect_credentials(payload: CredentialConnectRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DoctorPaymentConfig:
    return PaymentOnboardingService(db).connect_credentials(current_user, payload)


@router.get("/oauth/{provider}/authorize", response_model=OAuthStartRead)
def start_oauth(provider: PaymentProvider, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> OAuthStartRead:
    return OAuthStartRead(authorization_url=PaymentOnboardingService(db).oauth_url(provider, current_user))


@router.get("/oauth/{provider}/callback")
def oauth_callback(provider: PaymentProvider, code: str = Query(), state: str = Query(), db: Session = Depends(get_db)) -> RedirectResponse:
    PaymentOnboardingService(db).complete_oauth(provider, code, state)
    return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/dashboard/payments?connection=success")


@router.post("/bookings/{booking_id}/checkout", response_model=CheckoutRead)
def create_checkout(booking_id: uuid.UUID, db: Session = Depends(get_db)) -> CheckoutRead:
    booking = db.get(Booking, booking_id)
    event_type = db.get(EventType, booking.event_type_id) if booking else None
    if not booking or not event_type:
        raise AppError(404, "booking_not_found", "Booking not found.")
    return CheckoutService(db).create(booking, event_type)
