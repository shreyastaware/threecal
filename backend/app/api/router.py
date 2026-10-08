from fastapi import APIRouter

from app.domains.auth.router import router as auth_router
from app.domains.availability.router import router as availability_router
from app.domains.bookings.router import host_router as host_bookings_router
from app.domains.bookings.router import invitee_router as invitee_bookings_router
from app.domains.bookings.router import router as bookings_router
from app.domains.calendars.router import router as calendars_router
from app.domains.conferencing.router import router as conferencing_router
from app.domains.event_types.router import router as event_types_router
from app.domains.payments.router import router as payments_router
from app.domains.users.router import router as users_router
from app.domains.webhooks.router import router as webhooks_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(availability_router)
api_router.include_router(event_types_router)
api_router.include_router(payments_router)
api_router.include_router(host_bookings_router)
# Must precede bookings_router, whose /public/{username}/{event_slug} would capture /public/bookings/{id}.
api_router.include_router(invitee_bookings_router)
api_router.include_router(bookings_router)
api_router.include_router(webhooks_router)
api_router.include_router(calendars_router)
api_router.include_router(conferencing_router)
