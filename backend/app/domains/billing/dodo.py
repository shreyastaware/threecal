from typing import Any

import httpx

from app.core.config import settings


class DodoPaymentsError(RuntimeError):
    pass


class DodoPaymentsClient:
    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if not settings.dodo_payments_api_key:
            raise DodoPaymentsError("Dodo Payments is not configured.")
        try:
            response = httpx.request(
                method,
                f"{settings.dodo_payments_api_url.rstrip('/')}{path}",
                headers={"Authorization": f"Bearer {settings.dodo_payments_api_key}"},
                timeout=20,
                **kwargs,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DodoPaymentsError("Dodo Payments rejected the billing request.") from exc
        if not isinstance(payload, dict):
            raise DodoPaymentsError("Dodo Payments returned an invalid response.")
        return payload

    def create_customer(self, name: str, email: str, doctor_id: str) -> str:
        payload = self._request("POST", "/customers", json={"name": name, "email": email, "metadata": {"doctor_id": doctor_id}})
        return str(payload["customer_id"])

    def create_mandate_checkout(self, customer_id: str, doctor_id: str) -> str:
        if not settings.dodo_payments_product_id:
            raise DodoPaymentsError("The Dodo Payments mandate product is not configured.")
        payload = self._request(
            "POST",
            "/checkouts",
            json={
                "product_cart": [{"product_id": settings.dodo_payments_product_id, "quantity": 1}],
                "customer": {"customer_id": customer_id},
                "subscription_data": {"on_demand": {"mandate_only": True, "product_currency": "INR"}},
                "mandate_min_amount_inr_paise": 1500000,
                "metadata": {"doctor_id": doctor_id, "purpose": "platform_billing_mandate"},
                "return_url": f"{settings.frontend_url.rstrip('/')}/dashboard/billing?setup=complete",
            },
        )
        return str(payload["checkout_url"])

    def payment_method_belongs_to_customer(self, customer_id: str, payment_method_id: str) -> bool:
        payload = self._request("GET", f"/customers/{customer_id}/payment-methods")
        return any(item.get("payment_method_id") == payment_method_id and item.get("recurring_enabled") for item in payload.get("items", []))

    def subscription_belongs_to_customer(self, customer_id: str, subscription_id: str) -> bool:
        payload = self._request("GET", f"/subscriptions/{subscription_id}")
        customer = payload.get("customer", {})
        return isinstance(customer, dict) and customer.get("customer_id") == customer_id

    def charge_subscription(self, subscription_id: str, amount_minor: int, invoice_id: str) -> str:
        payload = self._request(
            "POST",
            f"/subscriptions/{subscription_id}/charge",
            json={"product_price": amount_minor, "product_currency": "INR", "metadata": {"invoice_id": invoice_id}},
        )
        return str(payload["payment_id"])

    def payment_status(self, payment_id: str) -> str:
        return str(self._request("GET", f"/payments/{payment_id}").get("status", "processing"))
