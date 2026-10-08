"""An in-memory Razorpay API used by payment tests (httpx MockTransport)."""

import hashlib
import hmac
import json
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from app.core.config import settings
from app.domains.payments.razorpay_route import RazorpayRouteGateway


KEY_ID = "rzp_test_key"
KEY_SECRET = "rzp_test_secret"
WEBHOOK_SECRET = "rzp_webhook_secret"
ACCOUNT_ID = "acc_TestLinked01"
STAKEHOLDER_ID = "sth_TestStake01"
PRODUCT_ID = "acc_prd_TestProd01"

ACCOUNT_PAYLOAD: dict[str, Any] = {
    "account_name": "Avery Stone",
    "account_email": "accounts@example.com",
    "business_type": "private_limited",
    "business_name": "Stone Health Private Limited",
    "branch_ifsc_code": "HDFC0001234",
    "account_number": "123456789012",
    "beneficiary_name": "Stone Health Private Limited",
    "phone": "+91 98765 43210",
    "business_category": "healthcare",
    "business_subcategory": "clinic",
    "street1": "507, Koramangala 1st block",
    "street2": "",
    "city": "Bengaluru",
    "state": "Karnataka",
    "postal_code": "560034",
    "pan": "AAACS1234C",
}


@dataclass
class FakeRazorpay:
    activation_status: str = "activated"
    requirements: list[dict[str, Any]] = field(default_factory=list)
    # path -> (status code, error description) to fail once.
    failures: dict[tuple[str, str], tuple[int, str]] = field(default_factory=dict)
    calls: list[tuple[str, str, dict[str, Any] | None]] = field(default_factory=list)
    order_count: int = 0
    refund_count: int = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"].startswith("Basic ")
        body = json.loads(request.content) if request.content else None
        path = request.url.path
        self.calls.append((request.method, path, body))
        failure = self.failures.pop((request.method, path), None)
        if failure:
            return httpx.Response(
                failure[0],
                json={"error": {"code": "BAD_REQUEST_ERROR", "description": failure[1], "field": None}},
            )
        product = {
            "id": PRODUCT_ID,
            "account_id": ACCOUNT_ID,
            "product_name": "route",
            "activation_status": self.activation_status,
            "requirements": self.requirements,
        }
        routes: dict[tuple[str, str], dict[str, Any]] = {
            ("POST", "/v2/accounts"): {"id": ACCOUNT_ID, "type": "route", "status": "created"},
            ("PATCH", f"/v2/accounts/{ACCOUNT_ID}"): {"id": ACCOUNT_ID},
            ("POST", f"/v2/accounts/{ACCOUNT_ID}/stakeholders"): {"id": STAKEHOLDER_ID, "entity": "stakeholder"},
            ("PATCH", f"/v2/accounts/{ACCOUNT_ID}/stakeholders/{STAKEHOLDER_ID}"): {"id": STAKEHOLDER_ID},
            ("POST", f"/v2/accounts/{ACCOUNT_ID}/products"): {
                **product,
                "activation_status": "needs_clarification",
                "requirements": [
                    {"field_reference": "settlements.account_number", "reason_code": "field_missing", "status": "required"}
                ],
            },
            ("PATCH", f"/v2/accounts/{ACCOUNT_ID}/products/{PRODUCT_ID}/"): product,
            ("GET", f"/v2/accounts/{ACCOUNT_ID}/products/{PRODUCT_ID}/"): product,
        }
        if (request.method, path) in routes:
            return httpx.Response(200, json=routes[(request.method, path)])
        if (request.method, path) == ("POST", "/v1/orders"):
            assert body is not None
            self.order_count += 1
            return httpx.Response(
                200,
                json={"id": f"order_Test{self.order_count}", "amount": body["amount"], "currency": body["currency"], "status": "created"},
            )
        if request.method == "POST" and path.startswith("/v1/payments/") and path.endswith("/refund"):
            self.refund_count += 1
            return httpx.Response(200, json={"id": f"rfnd_Test{self.refund_count}", "status": "processed"})
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND", "description": f"No route {path}"}})

    def paths(self, method: str | None = None) -> list[str]:
        return [path for call_method, path, _ in self.calls if method is None or call_method == method]

    def body(self, method: str, path: str) -> dict[str, Any]:
        for call_method, call_path, body in reversed(self.calls):
            if call_method == method and call_path == path:
                assert body is not None
                return body
        raise AssertionError(f"{method} {path} was not called")


@pytest.fixture
def razorpay(monkeypatch: pytest.MonkeyPatch) -> Generator[FakeRazorpay, None, None]:
    fake = FakeRazorpay()
    monkeypatch.setattr(settings, "razorpay_key_id", KEY_ID)
    monkeypatch.setattr(settings, "razorpay_key_secret", KEY_SECRET)
    monkeypatch.setattr(settings, "razorpay_webhook_secret", WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "razorpay_api_url", "https://api.razorpay.test")
    monkeypatch.setattr(settings, "platform_commission_bps", 1000)
    monkeypatch.setattr(RazorpayRouteGateway, "transport", httpx.MockTransport(fake.handler))
    yield fake


def sign_webhook(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def sign_checkout(order_id: str, payment_id: str) -> str:
    return hmac.new(KEY_SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
