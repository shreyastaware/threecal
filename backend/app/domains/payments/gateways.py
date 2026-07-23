import base64
import hashlib
import hmac
import json
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from app.domains.payments.models import PaymentProvider


class ProviderAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class PaymentRequest:
    booking_id: str
    doctor_id: str
    amount_minor: int
    currency: str
    customer_name: str
    customer_email: str


@dataclass(frozen=True)
class PaymentSession:
    payment_id: str
    client_secret: str | None = None
    checkout_url: str | None = None
    public_key: str | None = None


def format_minor_amount(amount_minor: int) -> str:
    return f"{amount_minor // 100}.{amount_minor % 100:02d}"


class PaymentGateway(ABC):
    provider: PaymentProvider

    def __init__(self, credentials: dict[str, str], account_id: str | None = None) -> None:
        self.credentials = credentials
        self.account_id = account_id

    @abstractmethod
    def register_webhook(self, endpoint_url: str, proposed_secret: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def create_payment(self, request: PaymentRequest) -> PaymentSession:
        raise NotImplementedError

    @abstractmethod
    def verify_webhook(self, body: bytes, headers: dict[str, str], secret: str) -> bool:
        raise NotImplementedError

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, Any]:
        try:
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderAPIError("The payment provider rejected the request.") from exc
        if not isinstance(result, dict):
            raise ProviderAPIError("The payment provider returned an invalid response.")
        return result


class StripeGateway(PaymentGateway):
    provider = PaymentProvider.STRIPE

    def _auth(self) -> tuple[str, str]:
        return (self.credentials["access_token"], "")

    def register_webhook(self, endpoint_url: str, proposed_secret: str) -> str:
        response = httpx.post(
            "https://api.stripe.com/v1/webhook_endpoints",
            auth=self._auth(),
            data={"url": endpoint_url, "enabled_events[]": "payment_intent.succeeded"},
            timeout=15,
        )
        return str(self._json(response).get("secret") or proposed_secret)

    def create_payment(self, request: PaymentRequest) -> PaymentSession:
        response = httpx.post(
            "https://api.stripe.com/v1/payment_intents",
            auth=self._auth(),
            data={
                "amount": request.amount_minor,
                "currency": request.currency.lower(),
                "metadata[booking_id]": request.booking_id,
                "metadata[doctor_id]": request.doctor_id,
                "receipt_email": request.customer_email,
                "automatic_payment_methods[enabled]": "true",
            },
            timeout=15,
        )
        payload = self._json(response)
        return PaymentSession(
            str(payload["id"]),
            client_secret=str(payload["client_secret"]),
            public_key=self.credentials.get("publishable_key"),
        )

    def verify_webhook(self, body: bytes, headers: dict[str, str], secret: str) -> bool:
        signature = headers.get("stripe-signature", "")
        parts = dict(item.split("=", 1) for item in signature.split(",") if "=" in item)
        try:
            timestamp = int(parts["t"])
        except (KeyError, ValueError):
            return False
        if abs(int(time.time()) - timestamp) > 300:
            return False
        expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, parts.get("v1", ""))


class RazorpayGateway(PaymentGateway):
    provider = PaymentProvider.RAZORPAY

    def _auth(self) -> tuple[str, str]:
        return self.credentials["api_key"], self.credentials["secret_key"]

    def _headers(self) -> dict[str, str]:
        access_token = self.credentials.get("access_token")
        return {"Authorization": f"Bearer {access_token}"} if access_token else {}

    def register_webhook(self, endpoint_url: str, proposed_secret: str) -> str:
        access_token = self.credentials.get("access_token")
        response = httpx.post(
            "https://api.razorpay.com/v1/webhooks",
            auth=None if access_token else self._auth(),
            headers=self._headers(),
            json={"url": endpoint_url, "secret": proposed_secret, "active": True, "events": ["order.paid"]},
            timeout=15,
        )
        self._json(response)
        return proposed_secret

    def create_payment(self, request: PaymentRequest) -> PaymentSession:
        access_token = self.credentials.get("access_token")
        response = httpx.post(
            "https://api.razorpay.com/v1/orders",
            auth=None if access_token else self._auth(),
            headers=self._headers(),
            json={"amount": request.amount_minor, "currency": request.currency, "notes": {"booking_id": request.booking_id, "doctor_id": request.doctor_id}},
            timeout=15,
        )
        payload = self._json(response)
        return PaymentSession(
            str(payload["id"]),
            public_key=self.credentials.get("public_token"),
        )

    def verify_webhook(self, body: bytes, headers: dict[str, str], secret: str) -> bool:
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, headers.get("x-razorpay-signature", ""))


class CashfreeGateway(PaymentGateway):
    provider = PaymentProvider.CASHFREE

    def _headers(self) -> dict[str, str]:
        access_token = self.credentials.get("access_token")
        if access_token:
            return {
                "Authorization": f"Bearer {access_token}",
                "x-api-version": "2025-01-01",
            }
        return {"x-client-id": self.credentials["api_key"], "x-client-secret": self.credentials["secret_key"], "x-api-version": "2025-01-01"}

    def register_webhook(self, endpoint_url: str, proposed_secret: str) -> str:
        if self.credentials.get("access_token"):
            return self.credentials["partner_api_key"]
        response = httpx.post(f"{self.credentials.get('payments_url', 'https://api.cashfree.com')}/pg/webhooks", headers=self._headers(), json={"webhook_url": endpoint_url}, timeout=15)
        self._json(response)
        return proposed_secret

    def create_payment(self, request: PaymentRequest) -> PaymentSession:
        response = httpx.post(
            f"{self.credentials.get('payments_url', 'https://api.cashfree.com')}/pg/orders",
            headers=self._headers(),
            json={
                "order_id": request.booking_id,
                "order_amount": format_minor_amount(request.amount_minor),
                "order_currency": request.currency,
                "customer_details": {"customer_id": request.booking_id, "customer_name": request.customer_name, "customer_email": request.customer_email, "customer_phone": "9999999999"},
                "order_tags": {"booking_id": request.booking_id, "doctor_id": request.doctor_id},
            },
            timeout=15,
        )
        payload = self._json(response)
        return PaymentSession(str(payload["order_id"]), client_secret=str(payload["payment_session_id"]))

    def verify_webhook(self, body: bytes, headers: dict[str, str], secret: str) -> bool:
        timestamp = headers.get("x-webhook-timestamp", "")
        digest = hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256).digest()
        return hmac.compare_digest(base64.b64encode(digest).decode(), headers.get("x-webhook-signature", ""))


class PayPalGateway(PaymentGateway):
    provider = PaymentProvider.PAYPAL

    def register_webhook(self, endpoint_url: str, proposed_secret: str) -> str:
        response = httpx.post(
            f"{self.credentials['api_url']}/v1/notifications/webhooks",
            headers={"Authorization": f"Bearer {self.credentials['access_token']}"},
            json={"url": endpoint_url, "event_types": [{"name": "PAYMENT.CAPTURE.COMPLETED"}]},
            timeout=15,
        )
        payload = self._json(response)
        return str(payload.get("id") or proposed_secret)

    def create_payment(self, request: PaymentRequest) -> PaymentSession:
        response = httpx.post(
            f"{self.credentials['api_url']}/v2/checkout/orders",
            headers={"Authorization": f"Bearer {self.credentials['access_token']}", "PayPal-Request-Id": request.booking_id},
            json={
                "intent": "CAPTURE",
                "purchase_units": [{"custom_id": request.booking_id, "invoice_id": request.booking_id, "amount": {"currency_code": request.currency, "value": format_minor_amount(request.amount_minor)}}],
            },
            timeout=15,
        )
        payload = self._json(response)
        approve = next((link.get("href") for link in payload.get("links", []) if link.get("rel") == "approve"), None)
        return PaymentSession(str(payload["id"]), checkout_url=str(approve) if approve else None)

    def verify_webhook(self, body: bytes, headers: dict[str, str], secret: str) -> bool:
        try:
            event = json.loads(body)
        except ValueError:
            return False
        try:
            response = httpx.post(
                f"{self.credentials['api_url']}/v1/notifications/verify-webhook-signature",
                headers={"Authorization": f"Bearer {self.credentials['access_token']}"},
                json={
                    "auth_algo": headers.get("paypal-auth-algo"),
                    "cert_url": headers.get("paypal-cert-url"),
                    "transmission_id": headers.get("paypal-transmission-id"),
                    "transmission_sig": headers.get("paypal-transmission-sig"),
                    "transmission_time": headers.get("paypal-transmission-time"),
                    "webhook_id": secret,
                    "webhook_event": event,
                },
                timeout=15,
            )
            return response.json().get("verification_status") == "SUCCESS"
        except (httpx.HTTPError, ValueError, AttributeError):
            return False


class BTCPayGateway(PaymentGateway):
    provider = PaymentProvider.BTCPAY

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"token {self.credentials['api_key']}"}

    def register_webhook(self, endpoint_url: str, proposed_secret: str) -> str:
        base = str(self.account_id).rstrip("/")
        response = httpx.post(
            f"{base}/api/v1/stores/{self.credentials['store_id']}/webhooks",
            headers=self._headers(),
            json={"url": endpoint_url, "secret": proposed_secret, "enabled": True, "automaticRedelivery": True},
            timeout=15,
        )
        self._json(response)
        return proposed_secret

    def create_payment(self, request: PaymentRequest) -> PaymentSession:
        base = str(self.account_id).rstrip("/")
        response = httpx.post(
            f"{base}/api/v1/stores/{self.credentials['store_id']}/invoices",
            headers=self._headers(),
            json={"amount": format_minor_amount(request.amount_minor), "currency": request.currency, "metadata": {"booking_id": request.booking_id, "doctor_id": request.doctor_id, "buyerEmail": request.customer_email}},
            timeout=15,
        )
        payload = self._json(response)
        return PaymentSession(str(payload["id"]), checkout_url=str(payload["checkoutLink"]))

    def verify_webhook(self, body: bytes, headers: dict[str, str], secret: str) -> bool:
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, headers.get("btcpay-sig", ""))


GATEWAYS: dict[PaymentProvider, type[PaymentGateway]] = {
    PaymentProvider.STRIPE: StripeGateway,
    PaymentProvider.RAZORPAY: RazorpayGateway,
    PaymentProvider.CASHFREE: CashfreeGateway,
    PaymentProvider.PAYPAL: PayPalGateway,
    PaymentProvider.BTCPAY: BTCPayGateway,
}


def create_gateway(provider: PaymentProvider, credentials: dict[str, str], account_id: str | None = None) -> PaymentGateway:
    return GATEWAYS[provider](credentials, account_id)


def generate_webhook_secret() -> str:
    return secrets.token_urlsafe(32)
