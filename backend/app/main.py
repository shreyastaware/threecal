import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.errors import AppError, UnhandledExceptionMiddleware, app_error_handler, unhandled_exception_handler
from app.core.logging import RequestLoggingMiddleware, configure_logging
from app.core.observability import init_sentry
from app.domains.calendars.handlers import register_calendar_handlers
from app.domains.conferencing.handlers import register_conferencing_handlers
from app.domains.notifications.handlers import register_notification_handlers

# Import domain models before creating metadata-managed tables.
from app.domains.auth.models import OAuthAccount  # noqa: F401, E402
from app.domains.availability.models import AvailabilityBreak, AvailabilityException, WorkingHour  # noqa: F401, E402
from app.domains.bookings.models import Booking  # noqa: F401, E402
from app.domains.calendars.models import BookingCalendarEvent, CalendarConnection, SelectedCalendar  # noqa: F401, E402
from app.domains.conferencing.models import BookingMeeting, ConferencingConnection  # noqa: F401, E402
from app.domains.event_types.models import EventType  # noqa: F401, E402
from app.domains.notifications.models import BookingReminder  # noqa: F401, E402
from app.domains.payments.models import PaymentAccount  # noqa: F401, E402
from app.domains.users.models import User  # noqa: F401, E402
from app.domains.webhooks.models import WebhookEvent  # noqa: F401, E402


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    scheduler = None
    if settings.scheduler_enabled:
        from app.jobs.scheduler import JobScheduler, build_jobs

        scheduler = JobScheduler(build_jobs(settings))
        scheduler.start()
    logger.info("application startup complete", extra={"environment": settings.environment})
    yield
    if scheduler is not None:
        await scheduler.stop()
    logger.info("application shutdown")


def create_app() -> FastAPI:
    configure_logging()
    init_sentry()
    # Meeting links (priority 10) and calendar sync (20) run before booking emails (100).
    register_conferencing_handlers()
    register_calendar_handlers()
    register_notification_handlers()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    # Added before CORS so it sits inside it and error responses still carry CORS headers.
    application.add_middleware(UnhandledExceptionMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Lets the frontend read how long to wait after a 429.
        expose_headers=["Retry-After"],
    )
    # Added after CORS so it is the outermost middleware and every response carries X-Request-ID.
    application.add_middleware(RequestLoggingMiddleware)
    application.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(Exception, unhandled_exception_handler)
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    @application.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
