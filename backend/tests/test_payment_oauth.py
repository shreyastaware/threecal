import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.domains.payments.models import PaymentProvider
from app.domains.payments.oauth_state import create_oauth_state, read_oauth_state


REGISTER_PAYLOAD = {
    "full_name": "Avery Stone",
    "email": "avery@example.com",
    "password": "strong-password",
}


def test_payment_oauth_state_is_compact_signed_and_provider_bound() -> None:
    doctor_id = uuid.uuid4()
    state = create_oauth_state(doctor_id, PaymentProvider.CASHFREE)

    assert len(state) <= 64
    assert read_oauth_state(state) == (doctor_id, PaymentProvider.CASHFREE)

    replacement = "A" if state[-1] != "A" else "B"
    with pytest.raises(ValueError):
        read_oauth_state(state[:-1] + replacement)


def test_razorpay_authorize_returns_provider_url(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "razorpay_client_id", "rzp_client")
    monkeypatch.setattr(settings, "razorpay_client_secret", "rzp_secret")
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    response = client.get("/api/v1/payments/oauth/razorpay/authorize")

    assert response.status_code == 200
    authorization_url = response.json()["authorization_url"]
    parsed = urlparse(authorization_url)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "auth.razorpay.com"
    assert query["client_id"] == ["rzp_client"]
    assert query["scope"] == ["read_write"]
    assert len(query["state"][0]) <= 64


def test_cashfree_authorize_is_created_server_side(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[tuple[str, dict[str, str], dict[str, str]]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"auth_link": "https://auth.cashfree.com/authorize-once"}

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, str],
        timeout: int,
    ) -> FakeResponse:
        assert timeout == 15
        requests.append((url, headers, json))
        return FakeResponse()

    monkeypatch.setattr(settings, "cashfree_oauth_client_id", "cf_client")
    monkeypatch.setattr(settings, "cashfree_partner_api_key", "cf_partner_secret")
    monkeypatch.setattr("app.domains.payments.service.httpx.post", fake_post)
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    response = client.get("/api/v1/payments/oauth/cashfree/authorize")

    assert response.status_code == 200
    assert response.json()["authorization_url"] == "https://auth.cashfree.com/authorize-once"
    assert requests[0][0].endswith("/partners/oauth/auth_link")
    assert requests[0][1] == {
        "x-partner-apikey": "cf_partner_secret",
        "oauth-client-id": "cf_client",
    }
    assert requests[0][2]["scope"] == "read_write"
    assert len(requests[0][2]["state"]) <= 64
