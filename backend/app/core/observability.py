import logging
import os

from app.core.config import Settings, settings

logger = logging.getLogger(__name__)


def _resolve_release(config: Settings) -> str | None:
    # Railway injects the deployed commit SHA; prefer an explicit SENTRY_RELEASE.
    return config.sentry_release or os.getenv("RAILWAY_GIT_COMMIT_SHA") or None


def init_sentry(config: Settings = settings) -> bool:
    """Initialise Sentry only when a DSN is configured. Returns True when enabled."""
    if not config.sentry_dsn:
        return False

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration, ignore_logger
    from sentry_sdk.integrations.starlette import StarletteIntegration

    from app.core.logging import ACCESS_LOGGER_NAME

    # Access log lines for 5xx responses are logged at ERROR; the exception itself is already captured.
    ignore_logger(ACCESS_LOGGER_NAME)

    sentry_sdk.init(
        dsn=config.sentry_dsn,
        environment=config.sentry_environment or config.environment,
        release=_resolve_release(config),
        traces_sample_rate=config.sentry_traces_sample_rate,
        # Patient/invitee data must not leave the app by default.
        send_default_pii=False,
        integrations=[
            StarletteIntegration(),
            FastApiIntegration(),
            # Breadcrumbs from INFO logs, events only from ERROR logs.
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )
    logger.info("sentry initialised", extra={"sentry_environment": config.sentry_environment or config.environment})
    return True
