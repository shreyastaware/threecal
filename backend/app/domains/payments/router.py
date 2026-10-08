import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.domains.auth.dependencies import get_current_user
from app.domains.payments.schemas import (
    CheckoutRead,
    PaymentAccountCreate,
    PaymentAccountRead,
    PaymentAccountUpdate,
    PaymentVerificationRead,
    PaymentVerificationRequest,
)
from app.domains.payments.service import (
    CheckoutService,
    PaymentAccountService,
    get_booking_for_payment,
)
from app.domains.users.models import User


router = APIRouter(prefix="/payments", tags=["payments"])


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


@router.post("/account/sync", response_model=PaymentAccountRead)
def sync_payment_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentAccountRead:
    return PaymentAccountService(db).sync(current_user)


@router.post(
    "/bookings/{booking_id}/checkout",
    response_model=CheckoutRead,
    dependencies=[Depends(rate_limit("checkout", limit=20, window_seconds=600))],
)
def create_checkout(booking_id: uuid.UUID, db: Session = Depends(get_db)) -> CheckoutRead:
    booking, event_type, host = get_booking_for_payment(db, booking_id)
    return CheckoutService(db).create(booking, event_type, host)


@router.post("/bookings/{booking_id}/verify", response_model=PaymentVerificationRead)
def verify_payment(
    booking_id: uuid.UUID,
    payload: PaymentVerificationRequest,
    db: Session = Depends(get_db),
) -> PaymentVerificationRead:
    booking, _, _ = get_booking_for_payment(db, booking_id)
    return CheckoutService(db).verify(booking, payload)
