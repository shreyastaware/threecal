import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_secret, encrypt_secret
from app.domains.payments.models import DoctorPaymentConfig, PaymentProvider


class PaymentConfigRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_doctor(self, doctor_id: uuid.UUID) -> DoctorPaymentConfig | None:
        return self.db.scalar(select(DoctorPaymentConfig).where(DoctorPaymentConfig.doctor_id == doctor_id))

    def save(
        self,
        doctor_id: uuid.UUID,
        provider: PaymentProvider,
        credentials: dict[str, str],
        account_id: str | None,
        webhook_secret: str,
    ) -> DoctorPaymentConfig:
        config = self.get_for_doctor(doctor_id)
        values = {
            "provider": provider,
            "account_id": account_id,
            "encrypted_api_key": encrypt_secret(json.dumps(credentials)),
            "encrypted_webhook_secret": encrypt_secret(webhook_secret),
        }
        if config:
            for key, value in values.items():
                setattr(config, key, value)
        else:
            config = DoctorPaymentConfig(doctor_id=doctor_id, **values)
            self.db.add(config)
        self.db.flush()
        return config

    @staticmethod
    def credentials(config: DoctorPaymentConfig) -> dict[str, str]:
        value = json.loads(decrypt_secret(config.encrypted_api_key))
        if not isinstance(value, dict) or not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
            raise ValueError("Stored payment credentials have an invalid format.")
        return value

    @staticmethod
    def webhook_secret(config: DoctorPaymentConfig) -> str:
        return decrypt_secret(config.encrypted_webhook_secret)
