"""In-process domain event bus.

Domains publish events (for example ``booking.confirmed``) after committing, and
other domains (notifications, calendar sync, conferencing) subscribe without
importing each other. Handlers for one event run sequentially in priority order
on a worker thread, so a lower-priority handler (emails) can rely on work done by
a higher-priority one (meeting links). Swap the dispatcher for a queue-backed one
when moving to multiple workers.
"""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)

BOOKING_CONFIRMED = "booking.confirmed"
BOOKING_CANCELLED = "booking.cancelled"
BOOKING_RESCHEDULED = "booking.rescheduled"


@dataclass(frozen=True)
class DomainEvent:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)


EventHandler = Callable[[DomainEvent], None]


class EventDispatcher(Protocol):
    def dispatch(self, job: Callable[[], None]) -> None: ...


class InlineDispatcher:
    """Runs handlers immediately; used in tests and jobs."""

    def dispatch(self, job: Callable[[], None]) -> None:
        job()


class ThreadPoolDispatcher:
    def __init__(self, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="domain-events")

    def dispatch(self, job: Callable[[], None]) -> None:
        self._executor.submit(job)


class EventBus:
    def __init__(self, dispatcher: EventDispatcher | None = None) -> None:
        self._handlers: dict[str, list[tuple[int, EventHandler]]] = {}
        self._lock = threading.Lock()
        self.dispatcher: EventDispatcher = dispatcher or ThreadPoolDispatcher()

    def subscribe(self, name: str, handler: EventHandler, priority: int = 100) -> None:
        """Lower priority runs first. Re-subscribing the same handler is a no-op."""
        with self._lock:
            handlers = self._handlers.setdefault(name, [])
            if any(existing is handler for _, existing in handlers):
                return
            handlers.append((priority, handler))
            handlers.sort(key=lambda item: item[0])

    def publish(self, event: DomainEvent) -> None:
        with self._lock:
            handlers = [handler for _, handler in self._handlers.get(event.name, [])]
        if handlers:
            self.dispatcher.dispatch(lambda: self._run(event, handlers))

    @staticmethod
    def _run(event: DomainEvent, handlers: list[EventHandler]) -> None:
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                # One failing subscriber must not stop the others.
                logger.exception("event handler failed", extra={"event": event.name, "handler": getattr(handler, "__qualname__", repr(handler))})


event_bus = EventBus()
