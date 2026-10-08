"""Pluggable request rate limiting.

The limiter is split into a storage backend (where hit counts live) and a FastAPI
dependency factory (how requests are keyed). The in-memory backend is per-process;
swap in a shared backend such as Redis via ``set_rate_limit_backend`` when running
more than one API instance.
"""

import json
import math
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Request, status

from app.core.config import settings
from app.core.errors import AppError


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RateLimitBackend(ABC):
    @abstractmethod
    def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        """Record one request for ``key`` and report whether it is within the limit."""
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        """Forget every recorded hit (used by tests and admin tooling)."""
        raise NotImplementedError


class InMemoryRateLimitBackend(RateLimitBackend):
    """Thread-safe sliding-window log kept in process memory."""

    def __init__(self, clock: Callable[[], float] = time.monotonic, sweep_every: int = 1000) -> None:
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._sweep_every = sweep_every
        self._calls = 0

    def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        now = self._clock()
        window_start = now - window_seconds
        with self._lock:
            self._calls += 1
            if self._calls % self._sweep_every == 0:
                self._sweep(window_start)

            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= window_start:
                hits.popleft()

            if len(hits) >= limit:
                retry_after = max(1, math.ceil(hits[0] + window_seconds - now))
                return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=retry_after)

            hits.append(now)
            return RateLimitResult(allowed=True, remaining=limit - len(hits), retry_after_seconds=0)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._calls = 0

    def _sweep(self, window_start: float) -> None:
        # Drop idle keys so memory does not grow with every client ever seen.
        # Keys with longer windows may be dropped early; that only makes the limiter more lenient.
        for key in [key for key, hits in self._hits.items() if not hits or hits[-1] <= window_start]:
            del self._hits[key]


_backend: RateLimitBackend = InMemoryRateLimitBackend()


def get_rate_limit_backend() -> RateLimitBackend:
    return _backend


def set_rate_limit_backend(backend: RateLimitBackend) -> None:
    global _backend
    _backend = backend


def client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded_for = request.headers.get("x-forwarded-for", "")
        # The left-most address is the original client; proxies append to the right.
        first_hop = forwarded_for.split(",")[0].strip()
        if first_hop:
            return first_hop
    return request.client.host if request.client else "unknown"


async def _body_email(request: Request) -> str | None:
    try:
        payload = json.loads(await request.body() or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None
    email = payload.get("email") if isinstance(payload, dict) else None
    return email.strip().lower() if isinstance(email, str) and email.strip() else None


def rate_limit(
    scope: str,
    *,
    limit: int,
    window_seconds: int,
    key_by_email: bool = False,
) -> Callable[[Request], Awaitable[None]]:
    """Build a dependency that allows ``limit`` requests per ``window_seconds``.

    Requests are counted per client IP. With ``key_by_email`` the JSON body's ``email``
    gets its own bucket too, so one account cannot be hammered from many addresses.
    """

    async def dependency(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return

        keys = [f"{scope}:ip:{client_ip(request)}"]
        if key_by_email:
            email = await _body_email(request)
            if email:
                keys.append(f"{scope}:email:{email}")

        backend = get_rate_limit_backend()
        for key in keys:
            result = backend.hit(key, limit=limit, window_seconds=window_seconds)
            if not result.allowed:
                raise AppError(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "rate_limited",
                    "Too many attempts. Please wait a moment and try again.",
                    headers={"Retry-After": str(result.retry_after_seconds)},
                )

    return dependency
