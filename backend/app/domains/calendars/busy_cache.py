"""Short-lived per-process cache of busy intervals from connected calendars.

Slot pages poll availability often; caching provider free/busy for a minute keeps
them fast and within provider rate limits. Swap for a shared cache (Redis) when
running more than one API instance.
"""

import threading
import time
import uuid
from datetime import datetime

from app.core.config import settings


Interval = tuple[datetime, datetime]

_lock = threading.Lock()
_entries: dict[tuple[uuid.UUID, str, str], tuple[float, list[Interval]]] = {}
# Bound memory use; the cache is purely an optimization.
_MAX_ENTRIES = 2048


def get(user_id: uuid.UUID, start: datetime, end: datetime) -> list[Interval] | None:
    key = (user_id, start.isoformat(), end.isoformat())
    with _lock:
        entry = _entries.get(key)
        if entry is None:
            return None
        expires_at, intervals = entry
        if expires_at < time.monotonic():
            _entries.pop(key, None)
            return None
        return list(intervals)


def put(user_id: uuid.UUID, start: datetime, end: datetime, intervals: list[Interval]) -> None:
    ttl = settings.calendar_busy_cache_seconds
    if ttl <= 0:
        return
    with _lock:
        if len(_entries) >= _MAX_ENTRIES:
            now = time.monotonic()
            for key in [key for key, (expires_at, _) in _entries.items() if expires_at < now]:
                _entries.pop(key, None)
            if len(_entries) >= _MAX_ENTRIES:
                _entries.clear()
        _entries[(user_id, start.isoformat(), end.isoformat())] = (time.monotonic() + ttl, list(intervals))


def invalidate(user_id: uuid.UUID) -> None:
    with _lock:
        for key in [key for key in _entries if key[0] == user_id]:
            _entries.pop(key, None)


def clear() -> None:
    with _lock:
        _entries.clear()
