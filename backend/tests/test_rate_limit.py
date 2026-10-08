import threading
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import InMemoryRateLimitBackend


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def limits_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", True)


def test_in_memory_backend_enforces_sliding_window() -> None:
    clock = FakeClock()
    backend = InMemoryRateLimitBackend(clock=clock)

    assert backend.hit("k", limit=2, window_seconds=60).allowed
    clock.now += 10
    assert backend.hit("k", limit=2, window_seconds=60).allowed
    blocked = backend.hit("k", limit=2, window_seconds=60)
    assert not blocked.allowed
    assert blocked.retry_after_seconds == 50
    # Other keys have their own budget.
    assert backend.hit("other", limit=2, window_seconds=60).allowed

    clock.now += 50
    assert backend.hit("k", limit=2, window_seconds=60).allowed
    assert not backend.hit("k", limit=2, window_seconds=60).allowed

    backend.reset()
    assert backend.hit("k", limit=2, window_seconds=60).allowed


def test_in_memory_backend_sweeps_idle_keys() -> None:
    clock = FakeClock()
    backend = InMemoryRateLimitBackend(clock=clock, sweep_every=3)
    backend.hit("a", limit=5, window_seconds=10)
    clock.now += 20
    backend.hit("b", limit=5, window_seconds=10)
    backend.hit("c", limit=5, window_seconds=10)
    assert "a" not in backend._hits


def test_in_memory_backend_is_thread_safe() -> None:
    backend = InMemoryRateLimitBackend()
    allowed: list[bool] = []
    lock = threading.Lock()

    def worker() -> None:
        for _ in range(50):
            result = backend.hit("shared", limit=100, window_seconds=60)
            with lock:
                allowed.append(result.allowed)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert allowed.count(True) == 100
    assert allowed.count(False) == 300


def test_login_is_rate_limited_with_retry_after(client: TestClient, limits_enabled: None) -> None:
    payload = {"email": "nobody@example.com", "password": "incorrect"}
    for _ in range(10):
        assert client.post("/api/v1/auth/login", json=payload).status_code == 401

    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 429
    assert response.json() == {
        "detail": "Too many attempts. Please wait a moment and try again.",
        "code": "rate_limited",
    }
    assert int(response.headers["retry-after"]) > 0


def test_rate_limit_disabled_by_setting(client: TestClient) -> None:
    payload = {"email": "nobody@example.com", "password": "incorrect"}
    for _ in range(15):
        assert client.post("/api/v1/auth/login", json=payload).status_code == 401


def test_forwarded_for_is_ignored_unless_trusted(client: TestClient, limits_enabled: None) -> None:
    for index in range(5):
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": f"user{index}@example.com"},
            headers={"X-Forwarded-For": f"203.0.113.{index}"},
        )
        assert response.status_code == 202

    spoofed = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "fresh@example.com"},
        headers={"X-Forwarded-For": "198.51.100.7"},
    )
    assert spoofed.status_code == 429


def test_forwarded_for_keys_by_client_when_trusted(
    client: TestClient, limits_enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    headers = {"X-Forwarded-For": "203.0.113.1, 10.0.0.1"}
    for index in range(5):
        response = client.post("/api/v1/auth/forgot-password", json={"email": f"user{index}@example.com"}, headers=headers)
        assert response.status_code == 202
    assert client.post("/api/v1/auth/forgot-password", json={"email": "x@example.com"}, headers=headers).status_code == 429

    other_client = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "y@example.com"},
        headers={"X-Forwarded-For": "203.0.113.2"},
    )
    assert other_client.status_code == 202


def test_email_bucket_limits_across_addresses(
    client: TestClient, limits_enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    for index in range(5):
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "Target@example.com"},
            headers={"X-Forwarded-For": f"203.0.113.{index}"},
        )
        assert response.status_code == 202

    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "target@example.com"},
        headers={"X-Forwarded-For": "198.51.100.99"},
    )
    assert response.status_code == 429


@pytest.mark.parametrize(
    ("path", "limit"),
    [
        ("/api/v1/auth/register", 10),
        ("/api/v1/auth/reset-password", 10),
        ("/api/v1/auth/verify-email", 10),
        ("/api/v1/public/nobody/intro/bookings", 10),
        (f"/api/v1/payments/bookings/{uuid.uuid4()}/checkout", 20),
    ],
)
def test_sensitive_routes_are_rate_limited(client: TestClient, limits_enabled: None, path: str, limit: int) -> None:
    for _ in range(limit):
        # Invalid bodies still count: the limiter runs before validation.
        assert client.post(path, json={}).status_code != 429
    assert client.post(path, json={}).status_code == 429


def test_resend_verification_is_rate_limited(client: TestClient, limits_enabled: None) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"full_name": "Avery Stone", "email": "avery@example.com", "password": "strong-password"},
    )
    statuses = [client.post("/api/v1/auth/resend-verification").status_code for _ in range(4)]
    assert statuses == [202, 202, 202, 429]
