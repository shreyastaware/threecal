import json
import logging
import time

from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.core.logging import JsonFormatter, LokiHandler, request_id_ctx
from app.core.observability import init_sentry


def test_responses_carry_generated_request_id(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert len(response.headers["x-request-id"]) == 32


def test_incoming_request_id_is_propagated(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "trace-abc-123"})

    assert response.headers["x-request-id"] == "trace-abc-123"


def test_json_formatter_includes_request_id_and_extras() -> None:
    token = request_id_ctx.set("req-1")
    try:
        record = logging.LogRecord("app.test", logging.WARNING, __file__, 1, "hello %s", ("world",), None)
        record.booking_id = "b-1"
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_ctx.reset(token)

    assert payload["message"] == "hello world"
    assert payload["level"] == "warning"
    assert payload["logger"] == "app.test"
    assert payload["request_id"] == "req-1"
    assert payload["booking_id"] == "b-1"
    assert "timestamp" in payload


def test_loki_handler_never_raises_when_push_fails() -> None:
    # Port 9 (discard) on localhost is closed; the push must fail silently in the background.
    handler = LokiHandler(url="http://127.0.0.1:9", labels={"app": "test"}, flush_interval=0.05, timeout=0.5)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("app.test.loki")
    logger.addHandler(handler)
    try:
        logger.error("this push will fail")
        time.sleep(0.2)
    finally:
        logger.removeHandler(handler)
        handler.close()
    assert handler.push_url == "http://127.0.0.1:9/loki/api/v1/push"


def test_sentry_is_disabled_without_dsn() -> None:
    assert init_sentry(Settings(sentry_dsn="")) is False


def test_unexpected_errors_return_json_500_with_cors_headers() -> None:
    from app.main import create_app

    application = create_app()

    @application.get("/boom")
    def boom() -> None:
        raise RuntimeError("database column missing")

    origin = settings.cors_origins[0]
    # Not used as a context manager, so startup (table creation, scheduler) does not run.
    response = TestClient(application, raise_server_exceptions=False).get("/boom", headers={"Origin": origin})

    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong. Please try again.", "code": "internal_error"}
    # Without this header the browser hides the response and reports "Failed to fetch".
    assert response.headers["access-control-allow-origin"] == origin
