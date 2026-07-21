from fastapi import APIRouter

from app.domains.auth.router import router as auth_router
from app.domains.availability.router import router as availability_router
from app.domains.billing.router import router as billing_router
from app.domains.bookings.router import router as bookings_router
from app.domains.event_types.router import router as event_types_router
from app.domains.payments.router import router as payments_router
from app.domains.users.router import router as users_router
from app.domains.webhooks.router import router as webhooks_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(availability_router)
api_router.include_router(billing_router)
api_router.include_router(event_types_router)
api_router.include_router(payments_router)
api_router.include_router(bookings_router)
api_router.include_router(webhooks_router)
