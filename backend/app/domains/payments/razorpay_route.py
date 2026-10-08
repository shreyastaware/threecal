"""Razorpay implementation of the platform payment gateway (Orders + Route).

API references (verified against razorpay.com/docs):
- POST  /v2/accounts                                   create Route linked account
- PATCH /v2/accounts/{account_id}                      update linked account
- POST  /v2/accounts/{account_id}/stakeholders         create stakeholder
- PATCH /v2/accounts/{account_id}/stakeholders/{id}    update stakeholder
- POST  /v2/accounts/{account_id}/products             request "route" product configuration
- PATCH /v2/accounts/{account_id}/products/{id}/       add settlement bank details + accept tnc
- GET   /v2/accounts/{account_id}/products/{id}/       fetch activation status
- POST  /v1/orders                                     order with Route ``transfers``
- POST  /v1/payments/{payment_id}/refund               refund with ``reverse_all``
"""

import hashlib
import hmac
from dataclasses import replace
from typing import Any

import httpx

from app.domains.payments.gateways import (
    GatewayEvent,
    HostPayoutProfile,
    LinkedAccountState,
    Order,
    OrderRequest,
    PaymentGateway,
    PayoutRequirement,
    ProviderAPIError,
    Refund,
)
from app.domains.payments.models import BusinessType, LinkedAccountStatus, PaymentProvider


# Business types whose PAN is the owner's personal PAN (sent on the stakeholder),
# per Razorpay Route's KYC matrix. Other types send a business PAN in legal_info.
_PERSONAL_PAN_BUSINESS_TYPES = {
    BusinessType.INDIVIDUAL,
    BusinessType.NOT_YET_REGISTERED,
    BusinessType.PROPRIETORSHIP,
}
_PAYMENT_EVENTS = {"payment.captured", "order.paid"}
_REFUND_EVENTS = {"refund.processed", "refund.failed", "refund.created"}
_PRODUCT_EVENT_PREFIX = "product.route."


class RazorpayRouteGateway(PaymentGateway):
    provider = PaymentProvider.RAZORPAY
    # Tests replace this with an httpx.MockTransport.
    transport: httpx.BaseTransport | None = None

    def __init__(self, *, key_id: str, key_secret: str, webhook_secret: str, api_url: str) -> None:
        self.public_key = key_id
        self._key_id = key_id
        self._key_secret = key_secret
        self._webhook_secret = webhook_secret
        self._api_url = api_url.rstrip("/")

    # ------------------------------------------------------------------ payouts

    def onboard_host(self, profile: HostPayoutProfile, current: LinkedAccountState) -> LinkedAccountState:
        state = current
        try:
            if not state.linked_account_id:
                account = self._request("POST", "/v2/accounts", self._account_payload(profile, create=True))
                state = replace(state, linked_account_id=str(account["id"]))
            if not state.stakeholder_id:
                stakeholder = self._request(
                    "POST",
                    f"/v2/accounts/{state.linked_account_id}/stakeholders",
                    self._stakeholder_payload(profile),
                )
                state = replace(state, stakeholder_id=str(stakeholder["id"]))
            if not state.product_configuration_id:
                product = self._request(
                    "POST",
                    f"/v2/accounts/{state.linked_account_id}/products",
                    {"product_name": "route", "tnc_accepted": True},
                )
                state = self._state_from_product(state, product)
            return self._configure_product(profile, state)
        except ProviderAPIError as exc:
            exc.partial_state = state
            raise

    def update_host(self, profile: HostPayoutProfile, current: LinkedAccountState) -> LinkedAccountState:
        if not current.linked_account_id or not current.stakeholder_id or not current.product_configuration_id:
            return self.onboard_host(profile, current)
        self._request(
            "PATCH",
            f"/v2/accounts/{current.linked_account_id}",
            self._account_payload(profile, create=False),
        )
        self._request(
            "PATCH",
            f"/v2/accounts/{current.linked_account_id}/stakeholders/{current.stakeholder_id}",
            self._stakeholder_payload(profile, include_email=False),
        )
        return self._configure_product(profile, current)

    def fetch_host_status(self, current: LinkedAccountState) -> LinkedAccountState:
        if not current.linked_account_id or not current.product_configuration_id:
            return current
        product = self._request(
            "GET",
            f"/v2/accounts/{current.linked_account_id}/products/{current.product_configuration_id}/",
        )
        return self._state_from_product(current, product)

    def _configure_product(self, profile: HostPayoutProfile, current: LinkedAccountState) -> LinkedAccountState:
        product = self._request(
            "PATCH",
            f"/v2/accounts/{current.linked_account_id}/products/{current.product_configuration_id}/",
            {
                "settlements": {
                    "account_number": profile.account_number,
                    "ifsc_code": profile.ifsc_code,
                    "beneficiary_name": profile.beneficiary_name,
                },
                "tnc_accepted": True,
            },
        )
        return self._state_from_product(current, product)

    @staticmethod
    def _state_from_product(current: LinkedAccountState, product: dict[str, Any]) -> LinkedAccountState:
        status = str(product.get("activation_status") or LinkedAccountStatus.REQUESTED.value)
        return LinkedAccountState(
            linked_account_id=current.linked_account_id,
            stakeholder_id=current.stakeholder_id,
            product_configuration_id=str(product.get("id") or current.product_configuration_id),
            activation_status=status,
            requirements=_parse_requirements(product.get("requirements")),
        )

    @staticmethod
    def _account_payload(profile: HostPayoutProfile, *, create: bool) -> dict[str, Any]:
        address: dict[str, str] = {
            "street1": profile.address.street1,
            "city": profile.address.city,
            "state": profile.address.state,
            "postal_code": profile.address.postal_code,
            "country": profile.address.country,
        }
        if profile.address.street2:
            address["street2"] = profile.address.street2
        payload: dict[str, Any] = {
            "phone": profile.phone,
            "legal_business_name": profile.legal_business_name,
            "customer_facing_business_name": profile.legal_business_name,
            "profile": {
                "category": profile.category,
                "subcategory": profile.subcategory,
                "addresses": {"registered": address},
            },
        }
        # contact_name must be 4-255 characters when sent.
        if len(profile.contact_name) >= 4:
            payload["contact_name"] = profile.contact_name
        if profile.pan and profile.business_type not in _PERSONAL_PAN_BUSINESS_TYPES:
            payload["legal_info"] = {"pan": profile.pan}
        if create:
            # email and business_type cannot be changed after creation.
            payload.update(
                {
                    "email": profile.email,
                    "type": "route",
                    "reference_id": profile.reference_id,
                    "business_type": profile.business_type.value,
                }
            )
        return payload

    @staticmethod
    def _stakeholder_payload(profile: HostPayoutProfile, *, include_email: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": profile.contact_name}
        if include_email:
            payload["email"] = profile.email
        if 8 <= len(profile.phone) <= 11:
            payload["phone"] = {"primary": profile.phone}
        if profile.pan and profile.business_type in _PERSONAL_PAN_BUSINESS_TYPES:
            payload["kyc"] = {"pan": profile.pan}
        return payload

    # -------------------------------------------------------------- collections

    def create_order(self, request: OrderRequest) -> Order:
        payload: dict[str, Any] = {
            "amount": request.amount_minor,
            "currency": request.currency,
            "receipt": request.receipt[:40],
            "notes": request.notes,
        }
        if request.transfers:
            payload["transfers"] = [
                {
                    "account": transfer.destination_account_id,
                    "amount": transfer.amount_minor,
                    "currency": transfer.currency,
                    "notes": transfer.notes,
                    "linked_account_notes": list(transfer.notes),
                    "on_hold": False,
                }
                for transfer in request.transfers
            ]
        order = self._request("POST", "/v1/orders", payload)
        return Order(order_id=str(order["id"]), amount_minor=int(order["amount"]), currency=str(order["currency"]))

    def verify_checkout_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        expected = hmac.new(self._key_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def verify_webhook(self, body: bytes, headers: dict[str, str]) -> bool:
        if not self._webhook_secret:
            return False
        expected = hmac.new(self._webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, headers.get("x-razorpay-signature", ""))

    def parse_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> GatewayEvent | None:
        event_type = str(payload["event"])
        body = payload.get("payload") or {}
        header_event_id = headers.get("x-razorpay-event-id")
        if event_type in _PAYMENT_EVENTS:
            payment = body["payment"]["entity"]
            order = (body.get("order") or {}).get("entity") or {}
            notes = _notes(order.get("notes")) or _notes(payment.get("notes"))
            amount = order["amount_paid"] if event_type == "order.paid" else payment["amount"]
            return GatewayEvent(
                event_id=header_event_id or f"{event_type}:{payment['id']}",
                event_type=event_type,
                payment_id=str(payment["id"]),
                order_id=str(order.get("id") or payment.get("order_id") or "") or None,
                amount_minor=int(amount),
                booking_id=notes.get("booking_id"),
            )
        if event_type.startswith(_PRODUCT_EVENT_PREFIX):
            product = body["merchant_product"]
            entity = product["entity"]
            data = product.get("data")
            requirements = data.get("requirements") if isinstance(data, dict) else None
            return GatewayEvent(
                event_id=header_event_id or f"{event_type}:{entity['id']}:{payload.get('created_at')}",
                event_type=event_type,
                linked_account_id=str(payload["account_id"]),
                activation_status=str(entity["activation_status"]),
                requirements=_parse_requirements(requirements),
            )
        if event_type in _REFUND_EVENTS:
            refund = body["refund"]["entity"]
            return GatewayEvent(
                event_id=header_event_id or f"{event_type}:{refund['id']}",
                event_type=event_type,
                refund_id=str(refund["id"]),
                refund_status=str(refund["status"]),
            )
        return None

    def refund(self, payment_id: str, amount_minor: int, *, reverse_transfers: bool, notes: dict[str, str]) -> Refund:
        payload: dict[str, Any] = {"amount": amount_minor, "notes": notes}
        if reverse_transfers:
            payload["reverse_all"] = True
        refund = self._request("POST", f"/v1/payments/{payment_id}/refund", payload)
        return Refund(refund_id=str(refund["id"]), status=str(refund.get("status") or "pending"))

    # ------------------------------------------------------------------- http

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            with httpx.Client(
                base_url=self._api_url,
                auth=(self._key_id, self._key_secret),
                timeout=20,
                transport=self.transport,
            ) as client:
                response = client.request(method, path, json=payload)
        except httpx.HTTPError as exc:
            raise ProviderAPIError("Could not reach Razorpay. Please try again in a moment.") from exc
        try:
            data = response.json()
        except ValueError:
            data = None
        if response.is_error:
            error = data.get("error") if isinstance(data, dict) else None
            if isinstance(error, dict):
                raise ProviderAPIError(
                    str(error.get("description") or "Razorpay rejected the request."),
                    code=str(error.get("code") or "") or None,
                    field=str(error.get("field") or "") or None,
                )
            raise ProviderAPIError("Razorpay rejected the request.")
        if not isinstance(data, dict):
            raise ProviderAPIError("Razorpay returned an invalid response.")
        return data


def _notes(value: object) -> dict[str, str]:
    # Razorpay returns an empty list instead of an object when no notes exist.
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items()}
    return {}


def _parse_requirements(value: object) -> list[PayoutRequirement]:
    if not isinstance(value, list):
        return []
    return [
        PayoutRequirement(
            field_reference=str(item.get("field_reference") or ""),
            reason_code=str(item.get("reason_code") or ""),
            status=str(item.get("status") or ""),
            description=str(item["description"]) if item.get("description") else None,
        )
        for item in value
        if isinstance(item, dict)
    ]
