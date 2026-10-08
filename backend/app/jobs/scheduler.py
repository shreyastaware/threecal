import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import Settings
from app.jobs.backup_database import backup_database
from app.jobs.expire_pending_bookings import expire_pending_bookings
from app.jobs.runner import execute_job
from app.jobs.send_booking_reminders import send_booking_reminders

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduledJob:
    name: str
    func: Callable[[], Any]
    # Returns how long to sleep before the next run.
    next_delay: Callable[[datetime], timedelta]


def every(interval: timedelta) -> Callable[[datetime], timedelta]:
    return lambda _now: interval


def daily_at(hour_utc: int) -> Callable[[datetime], timedelta]:
    def delay(now: datetime) -> timedelta:
        next_run = now.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run - now

    return delay


def build_jobs(config: Settings) -> list[ScheduledJob]:
    # Add the appointment reminders job here once it exists.
    return [
        ScheduledJob(
            name="expire_pending_bookings",
            func=expire_pending_bookings,
            next_delay=every(timedelta(minutes=config.expire_pending_bookings_interval_minutes)),
        ),
        # Appointment reminders (claims each reminder before sending, so overlapping runs are safe).
        ScheduledJob(
            name="send_booking_reminders",
            func=send_booking_reminders,
            next_delay=every(timedelta(minutes=config.send_booking_reminders_interval_minutes)),
        ),
        ScheduledJob(
            name="backup_database",
            func=backup_database,
            next_delay=daily_at(config.backup_hour_utc),
        ),
    ]


class JobScheduler:
    """Minimal in-process scheduler.

    SQLite lives on the API service's Railway volume, and a Railway volume can only be attached to
    one service, so separate cron services cannot reach the database. Jobs therefore run inside the
    API process (a single replica, since Railway volumes do not support replicas). Each job runs in a
    worker thread so the event loop keeps serving requests.
    """

    def __init__(self, jobs: list[ScheduledJob]) -> None:
        self.jobs = jobs
        self._tasks: list[asyncio.Task[None]] = []

    def start(self) -> None:
        for job in self.jobs:
            self._tasks.append(asyncio.create_task(self._loop(job), name=f"job:{job.name}"))
        logger.info("job scheduler started", extra={"jobs": [job.name for job in self.jobs]})

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _loop(self, job: ScheduledJob) -> None:
        while True:
            delay = job.next_delay(datetime.now(timezone.utc))
            await asyncio.sleep(delay.total_seconds())
            await asyncio.to_thread(execute_job, job.name, job.func)
