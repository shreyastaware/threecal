import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import status
from jose import JWTError, jwt  # type: ignore[import-untyped]
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.domains.bookings.models import Booking, BookingStatus
from app.domains.event_types.models import EventType
from app.domains.payments.gateways import PaymentRequest, ProviderAPIError, create_gateway, generate_webhook_secret
from app.domains.payments.models import DoctorPaymentConfig, PaymentProvider
from app.domains.payments.repository import PaymentConfigRepository
from app.domains.payments.schemas import CheckoutRead, CredentialConnectRequest
from app.domains.users.models import User


class PaymentOnboardingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.configs = PaymentConfigRepository(db)

    def connect_credentials(self, doctor: User, payload: CredentialConnectRequest) -> DoctorPaymentConfig:
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
        config = self.configs.save(doctor.id, payload.provider, credentials, account_id, secret)
        self.db.commit()
        self.db.refresh(config)
        return config

    def oauth_url(self, provider: PaymentProvider, doctor: User) -> str:
        state_token = jwt.encode(
            {"sub": str(doctor.id), "provider": provider.value, "type": "payment_oauth", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        redirect_uri = f"{settings.public_api_url.rstrip('/')}{settings.api_v1_prefix}/payments/oauth/{provider.value}/callback"
        if provider == PaymentProvider.STRIPE:
            if not settings.stripe_client_id:
                raise AppError(503, "provider_not_configured", "Stripe OAuth is not configured.")
            query = urlencode({"response_type": "code", "client_id": settings.stripe_client_id, "scope": "read_write", "redirect_uri": redirect_uri, "state": state_token})
            return f"https://connect.stripe.com/oauth/authorize?{query}"
        if provider == PaymentProvider.PAYPAL:
            if not settings.paypal_client_id:
                raise AppError(503, "provider_not_configured", "PayPal OAuth is not configured.")
            query = urlencode({"client_id": settings.paypal_client_id, "response_type": "code", "scope": "openid https://uri.paypal.com/services/paypalattributes", "redirect_uri": redirect_uri, "state": state_token})
            return f"https://www.sandbox.paypal.com/signin/authorize?{query}"
        raise AppError(422, "oauth_not_supported", "This provider uses credential onboarding.")

    def complete_oauth(self, provider: PaymentProvider, code: str, state_token: str) -> DoctorPaymentConfig:
        try:
            state_data = jwt.decode(state_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            doctor_id = uuid.UUID(state_data["sub"])
            if state_data.get("type") != "payment_oauth" or state_data.get("provider") != provider.value:
                raise ValueError
        except (JWTError, KeyError, ValueError) as exc:
            raise AppError(400, "invalid_oauth_state", "The OAuth state is invalid or expired.") from exc

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
                credentials = {"access_token": str(data["access_token"]), "refresh_token": str(data.get("refresh_token", ""))}
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
            else:
                raise AppError(422, "oauth_not_supported", "This provider uses credential onboarding.")
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise AppError(502, "oauth_exchange_failed", "The provider did not complete OAuth.") from exc

        gateway = create_gateway(provider, credentials, account_id)
        try:
            webhook_secret = gateway.register_webhook(self._webhook_url(provider, doctor_id), generate_webhook_secret())
        except (ProviderAPIError, httpx.HTTPError) as exc:
            raise AppError(502, "webhook_registration_failed", str(exc)) from exc
        config = self.configs.save(doctor_id, provider, credentials, account_id, webhook_secret)
        self.db.commit()
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
        return CheckoutRead(provider=config.provider, provider_payment_id=result.payment_id, client_secret=result.client_secret, checkout_url=result.checkout_url)
