import atexit
import json
import logging
import queue
import sys
import threading
import time
import uuid
from collections.abc import Awaitable, Callable, MutableMapping
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import Settings, settings

# Request-scoped correlation id, attached to every log line emitted while handling a request.
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

ACCESS_LOGGER_NAME = "app.access"
REQUEST_ID_HEADER = "x-request-id"
_SKIPPED_ACCESS_PATHS = frozenset({"/health"})
_MAX_REQUEST_ID_LENGTH = 128

# Attributes present on every LogRecord; anything else was passed via `extra=` and is emitted as a field.
_RESERVED_RECORD_ATTRS = frozenset(
    vars(logging.LogRecord("", logging.INFO, "", 0, "", None, None)).keys()
) | {"message", "asctime", "taskName"}

# Loggers whose records must never be shipped to Loki (the pusher itself uses httpx).
_LOKI_IGNORED_LOGGERS = ("httpx", "httpcore")


class JsonFormatter(logging.Formatter):
    """Single-line JSON log records suited for Railway stdout capture and Grafana Loki."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or request_id_ctx.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str)


class LokiHandler(logging.Handler):
    """Non-blocking Grafana Loki push handler.

    Records are queued and shipped in batches by a daemon thread. Push failures are swallowed so
    logging can never take the application down; stdout logs remain the source of truth.
    """

    def __init__(
        self,
        *,
        url: str,
        labels: dict[str, str],
        username: str = "",
        password: str = "",
        batch_size: int = 200,
        flush_interval: float = 2.0,
        max_queue_size: int = 10_000,
        timeout: float = 5.0,
    ) -> None:
        super().__init__()
        self.push_url = _loki_push_url(url)
        self.labels = labels
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._queue: queue.Queue[tuple[str, str, str]] = queue.Queue(maxsize=max_queue_size)
        self._stop = threading.Event()
        auth = (username, password) if username else None
        self._client = httpx.Client(auth=auth, timeout=timeout)
        self._thread = threading.Thread(target=self._run, name="loki-log-pusher", daemon=True)
        self._thread.start()
        atexit.register(self.close)

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(_LOKI_IGNORED_LOGGERS):
            return
        try:
            entry = (str(time.time_ns()), record.levelname.lower(), self.format(record))
            self._queue.put_nowait(entry)
        except queue.Full:
            # Drop logs rather than block request handling when Loki is unreachable.
            pass
        except Exception:
            self.handleError(record)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._flush(wait=self.flush_interval)
        self._flush(wait=0)

    def _flush(self, *, wait: float) -> None:
        batch: list[tuple[str, str, str]] = []
        deadline = time.monotonic() + wait
        while len(batch) < self.batch_size:
            remaining = deadline - time.monotonic()
            try:
                if remaining > 0:
                    batch.append(self._queue.get(timeout=remaining))
                else:
                    batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if batch:
            self._push(batch)

    def _push(self, batch: list[tuple[str, str, str]]) -> None:
        streams: dict[str, list[list[str]]] = {}
        for timestamp, level, line in batch:
            streams.setdefault(level, []).append([timestamp, line])
        body: dict[str, list[dict[str, Any]]] = {
            "streams": [
                {"stream": {**self.labels, "level": level}, "values": values}
                for level, values in streams.items()
            ]
        }
        try:
            response = self._client.post(self.push_url, json=body)
            if response.status_code >= 400:
                sys.stderr.write(f"loki push rejected: {response.status_code} {response.text[:200]}\n")
        except Exception as exc:  # noqa: BLE001 - never let log shipping crash the app
            sys.stderr.write(f"loki push failed: {exc!r}\n")

    def close(self) -> None:
        if not self._stop.is_set():
            self._stop.set()
            self._thread.join(timeout=5)
            self._client.close()
        super().close()


def _loki_push_url(url: str) -> str:
    url = url.rstrip("/")
    return url if url.endswith("/loki/api/v1/push") else f"{url}/loki/api/v1/push"


_configured = False


def configure_logging(config: Settings = settings) -> None:
    """Route all logging (app, uvicorn, jobs) through JSON stdout and optionally Loki. Idempotent."""
    global _configured
    if _configured:
        return
    _configured = True

    level = logging.getLevelName(config.log_level.upper())
    if not isinstance(level, int):
        level = logging.INFO

    formatter = JsonFormatter()
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    handlers: list[logging.Handler] = [stdout_handler]

    if config.loki_url:
        loki_handler = LokiHandler(
            url=config.loki_url,
            username=config.loki_username,
            password=config.loki_password,
            labels={"app": "threecal-api", "environment": config.environment},
        )
        loki_handler.setFormatter(formatter)
        handlers.append(loki_handler)

    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(level)

    # Let uvicorn logs flow through the root JSON handlers; the request middleware replaces access logs.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers = []
    access_logger.propagate = False
    for noisy in _LOKI_IGNORED_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)


ASGIScope = MutableMapping[str, Any]
ASGIMessage = MutableMapping[str, Any]
ASGIReceive = Callable[[], Awaitable[ASGIMessage]]
ASGISend = Callable[[ASGIMessage], Awaitable[None]]
ASGIApp = Callable[[ASGIScope, ASGIReceive, ASGISend], Awaitable[None]]


def _incoming_request_id(scope: ASGIScope) -> str:
    for name, value in scope.get("headers", []):
        if name == REQUEST_ID_HEADER.encode():
            candidate = value.decode("latin-1").strip()
            if candidate and len(candidate) <= _MAX_REQUEST_ID_LENGTH and candidate.isprintable():
                return candidate
    return uuid.uuid4().hex


class RequestLoggingMiddleware:
    """Assigns/propagates X-Request-ID and emits one structured access log line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger(ACCESS_LOGGER_NAME)

    async def __call__(self, scope: ASGIScope, receive: ASGIReceive, send: ASGISend) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope)
        request_id_ctx.set(request_id)
        _tag_sentry_scope(request_id)
        status_code = 500
        started = time.perf_counter()

        async def send_with_request_id(message: ASGIMessage) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            path = scope.get("path", "")
            if path not in _SKIPPED_ACCESS_PATHS:
                duration_ms = round((time.perf_counter() - started) * 1000, 2)
                level = logging.ERROR if status_code >= 500 else logging.INFO
                self.logger.log(
                    level,
                    "%s %s %s",
                    scope.get("method", ""),
                    path,
                    status_code,
                    extra={
                        "method": scope.get("method", ""),
                        "path": path,
                        "status": status_code,
                        "duration_ms": duration_ms,
                    },
                )


def _tag_sentry_scope(request_id: str) -> None:
    try:
        import sentry_sdk

        sentry_sdk.set_tag("request_id", request_id)
    except Exception:  # noqa: BLE001 - Sentry is optional
        pass
