import logging
import sys
import time
from collections.abc import Callable
from typing import Any

from app.core.logging import configure_logging
from app.core.observability import init_sentry

logger = logging.getLogger("app.jobs")


def execute_job(name: str, job: Callable[[], Any]) -> bool:
    """Run a job with structured start/finish/failure logs. Returns False when the job raised."""
    started = time.perf_counter()
    logger.info("job started", extra={"job": name})
    try:
        result = job()
    except Exception:
        # logger.exception is also reported to Sentry through its logging integration.
        logger.exception(
            "job failed",
            extra={"job": name, "duration_ms": round((time.perf_counter() - started) * 1000, 2)},
        )
        return False
    logger.info(
        "job finished",
        extra={"job": name, "result": result, "duration_ms": round((time.perf_counter() - started) * 1000, 2)},
    )
    return True


def run_job(name: str, job: Callable[[], Any]) -> None:
    """CLI entrypoint for `python -m app.jobs.<name>`; exits non-zero on failure so cron runners flag it."""
    configure_logging()
    init_sentry()
    succeeded = execute_job(name, job)
    _flush_sentry()
    if not succeeded:
        sys.exit(1)


def _flush_sentry() -> None:
    # Short-lived processes must flush queued Sentry events before exiting.
    import sentry_sdk

    sentry_sdk.flush(timeout=5)
