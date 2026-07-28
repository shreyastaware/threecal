import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.domains.bookings.models import Booking, BookingStatus
from app.domains.event_types.models import EventType
from app.domains.payments.gateways import PaymentRequest, ProviderAPIError, create_gateway, generate_webhook_secret
from app.domains.payments.models import DoctorPaymentConfig, PaymentProvider
from app.domains.payments.oauth_state import create_oauth_state, read_oauth_state
from app.domains.payments.repository import PaymentConfigRepository
from app.domains.payments.schemas import CheckoutRead, CredentialConnectRequest
from app.domains.users.models import User


class PaymentOnboardingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.configs = PaymentConfigRepository(db)

    def connect_credentials(self, doctor: User, payload: CredentialConnectRequest) -> DoctorPaymentConfig:
        self._ensure_provider_can_be_connected(doctor.id)
        credentials = {"api_key": payload.api_key.get_secret_value()}
        if payload.secret_key:
            credentials["secret_key"] = payload.secret_key.get_secret_value()
        account_id = payload.account_id
        if payload.provider == PaymentProvider.BTCPAY:
            credentials["store_id"] = payload.store_id or ""
            account_id = payload.store_url
        proposed_secret = payload.webhook_secret.get_secret_value() if payload.webhook_secret else generate_webhook_secret()
        gateway = create_gateway(payload.provider, credentials, account_id)
        try:
            secret = gateway.register_webhook(self._webhook_url(payload.provider, doctor.id), proposed_secret)
        except (ProviderAPIError, httpx.HTTPError) as exc:
            raise AppError(status.HTTP_502_BAD_GATEWAY, "provider_connection_failed", str(exc)) from exc
        return self._create_connection(doctor.id, payload.provider, credentials, account_id, secret)

    def oauth_url(self, provider: PaymentProvider, doctor: User) -> str:
        self._ensure_provider_can_be_connected(doctor.id)
        try:
            state_token = create_oauth_state(doctor.id, provider)
        except ValueError as exc:
            raise AppError(422, "oauth_not_supported", str(exc)) from exc
        redirect_uri = f"{settings.public_api_url.rstrip('/')}{settings.api_v1_prefix}/payments/oauth/{provider.value}/callback"
        if provider == PaymentProvider.STRIPE:
            if not settings.stripe_client_id or not settings.stripe_client_secret:
                raise AppError(503, "provider_not_configured", "Stripe OAuth is not configured.")
            query = urlencode({"response_type": "code", "client_id": settings.stripe_client_id, "scope": "read_write", "redirect_uri": redirect_uri, "state": state_token})
            return f"https://connect.stripe.com/oauth/authorize?{query}"
        if provider == PaymentProvider.PAYPAL:
            if not settings.paypal_client_id or not settings.paypal_client_secret:
                raise AppError(503, "provider_not_configured", "PayPal OAuth is not configured.")
            query = urlencode({"client_id": settings.paypal_client_id, "response_type": "code", "scope": "openid https://uri.paypal.com/services/paypalattributes", "redirect_uri": redirect_uri, "state": state_token})
            return f"{settings.paypal_authorize_url}?{query}"
        if provider == PaymentProvider.RAZORPAY:
            if not settings.razorpay_client_id or not settings.razorpay_client_secret:
                raise AppError(503, "provider_not_configured", "Razorpay OAuth is not configured.")
            query = urlencode({"client_id": settings.razorpay_client_id, "response_type": "code", "redirect_uri": redirect_uri, "scope": "read_write", "state": state_token})
            return f"https://auth.razorpay.com/authorize?{query}"
        if provider == PaymentProvider.CASHFREE:
            if not settings.cashfree_oauth_client_id or not settings.cashfree_partner_api_key:
                raise AppError(503, "provider_not_configured", "Cashfree OAuth is not configured.")
            try:
                response = httpx.post(
                    f"{settings.cashfree_api_url.rstrip('/')}/partners/oauth/auth_link",
                    headers={
                        "x-partner-apikey": settings.cashfree_partner_api_key,
                        "oauth-client-id": settings.cashfree_oauth_client_id,
                    },
                    json={
                        "response_type": "code",
                        "scope": "read_write",
                        "state": state_token,
                        "merchant_id": str(doctor.id),
                    },
                    timeout=15,
                )
                response.raise_for_status()
                authorization_url = response.json()["auth_link"]
                if not isinstance(authorization_url, str):
                    raise ValueError
                return authorization_url
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                raise AppError(502, "oauth_authorization_failed", "Cashfree did not create an authorization link.") from exc
        raise AppError(422, "oauth_not_supported", "This provider does not support OAuth.")

    def complete_oauth(self, provider: PaymentProvider, code: str, state_token: str) -> DoctorPaymentConfig:
        try:
            doctor_id, state_provider = read_oauth_state(state_token)
            if state_provider != provider:
                raise ValueError
        except ValueError as exc:
            raise AppError(400, "invalid_oauth_state", "The OAuth state is invalid or expired.") from exc

        self._ensure_provider_can_be_connected(doctor_id)
        redirect_uri = f"{settings.public_api_url.rstrip('/')}{settings.api_v1_prefix}/payments/oauth/{provider.value}/callback"
        try:
            if provider == PaymentProvider.STRIPE:
                response = httpx.post(
                    "https://connect.stripe.com/oauth/token",
                    auth=(settings.stripe_client_secret, ""),
                    data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()
                credentials = {
                    "access_token": str(data["access_token"]),
                    "refresh_token": str(data.get("refresh_token", "")),
                    "publishable_key": str(data.get("stripe_publishable_key", "")),
                }
                account_id = str(data["stripe_user_id"])
            elif provider == PaymentProvider.PAYPAL:
                response = httpx.post(
                    f"{settings.paypal_api_url}/v1/oauth2/token",
                    auth=(settings.paypal_client_id, settings.paypal_client_secret),
                    data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()
                credentials = {"access_token": str(data["access_token"]), "refresh_token": str(data.get("refresh_token", "")), "api_url": settings.paypal_api_url}
                account_id = str(data.get("payer_id") or data.get("user_id") or doctor_id)
            elif provider == PaymentProvider.RAZORPAY:
                response = httpx.post(
                    "https://auth.razorpay.com/token",
                    json={
                        "client_id": settings.razorpay_client_id,
                        "client_secret": settings.razorpay_client_secret,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                        "code": code,
                        "mode": settings.razorpay_oauth_mode,
                    },
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()
                credentials = {
                    "access_token": str(data["access_token"]),
                    "refresh_token": str(data.get("refresh_token", "")),
                    "public_token": str(data.get("public_token", "")),
                }
                account_id = str(data["razorpay_account_id"])
            elif provider == PaymentProvider.CASHFREE:
                response = httpx.post(
                    f"{settings.cashfree_api_url.rstrip('/')}/partners/oauth/token",
                    headers={
                        "x-partner-apikey": settings.cashfree_partner_api_key,
                        "oauth-client-id": settings.cashfree_oauth_client_id,
                    },
                    json={
                        "grant_type": "authorization_code",
                        "code": code,
                    },
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()
                credentials = {
                    "access_token": str(data["access_token"]),
                    "refresh_token": str(data.get("refresh_token", "")),
                    "partner_api_key": settings.cashfree_partner_api_key,
                    "payments_url": settings.cashfree_payments_url.rstrip("/"),
                }
                account_id = str(data["merchant_id"])
            else:
                raise AppError(422, "oauth_not_supported", "This provider does not support OAuth.")
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise AppError(502, "oauth_exchange_failed", "The provider did not complete OAuth.") from exc

        gateway = create_gateway(provider, credentials, account_id)
        try:
            webhook_secret = gateway.register_webhook(self._webhook_url(provider, doctor_id), generate_webhook_secret())
        except (ProviderAPIError, httpx.HTTPError) as exc:
            raise AppError(502, "webhook_registration_failed", str(exc)) from exc
        return self._create_connection(doctor_id, provider, credentials, account_id, webhook_secret)

    def _ensure_provider_can_be_connected(self, doctor_id: uuid.UUID) -> None:
        if self.configs.get_for_doctor(doctor_id):
            raise AppError(
                status.HTTP_409_CONFLICT,
                "payment_provider_already_connected",
                "A payment provider is already connected. Only one payment connection is allowed.",
            )

    def _create_connection(
        self,
        doctor_id: uuid.UUID,
        provider: PaymentProvider,
        credentials: dict[str, str],
        account_id: str | None,
        webhook_secret: str,
    ) -> DoctorPaymentConfig:
        try:
            config = self.configs.create(
                doctor_id,
                provider,
                credentials,
                account_id,
                webhook_secret,
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                status.HTTP_409_CONFLICT,
                "payment_provider_already_connected",
                "A payment provider is already connected. Only one payment connection is allowed.",
            ) from exc
        self.db.refresh(config)
        return config

    @staticmethod
    def _webhook_url(provider: PaymentProvider, doctor_id: uuid.UUID) -> str:
        return f"{settings.public_api_url.rstrip('/')}{settings.api_v1_prefix}/webhooks/{provider.value}/{doctor_id}"


class CheckoutService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.configs = PaymentConfigRepository(db)

    def create(self, booking: Booking, event_type: EventType) -> CheckoutRead:
        if booking.status != BookingStatus.PENDING or booking.booking_amount <= 0:
            raise AppError(409, "booking_not_payable", "This booking does not require a payment.")
        expires_at = booking.payment_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise AppError(410, "payment_window_expired", "The booking payment window has expired.")
        config = self.configs.get_for_doctor(booking.host_id)
        if not config:
            raise AppError(409, "payment_provider_missing", "The doctor has not connected a payment provider.")
        gateway = create_gateway(config.provider, self.configs.credentials(config), config.account_id)
        try:
            result = gateway.create_payment(
                PaymentRequest(str(booking.id), str(booking.host_id), booking.booking_amount, event_type.currency, booking.invitee_name, booking.invitee_email)
            )
        except (ProviderAPIError, httpx.HTTPError) as exc:
            raise AppError(502, "checkout_creation_failed", str(exc)) from exc
        booking.provider_payment_id = result.payment_id
        self.db.commit()
        return CheckoutRead(
            provider=config.provider,
            provider_payment_id=result.payment_id,
            client_secret=result.client_secret,
            checkout_url=result.checkout_url,
            public_key=result.public_key,
        )
