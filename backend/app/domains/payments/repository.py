import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_secret, encrypt_secret
from app.domains.payments.models import (
    BusinessType,
    DoctorPaymentConfig,
    PaymentAccount,
    PaymentProvider,
)


class PaymentConfigRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_doctor(self, doctor_id: uuid.UUID) -> DoctorPaymentConfig | None:
        return self.db.scalar(select(DoctorPaymentConfig).where(DoctorPaymentConfig.doctor_id == doctor_id))

    def create(
        self,
        doctor_id: uuid.UUID,
        provider: PaymentProvider,
        credentials: dict[str, str],
        account_id: str | None,
        webhook_secret: str,
    ) -> DoctorPaymentConfig:
        config = DoctorPaymentConfig(
            doctor_id=doctor_id,
            provider=provider,
            account_id=account_id,
            encrypted_api_key=encrypt_secret(json.dumps(credentials)),
            encrypted_webhook_secret=encrypt_secret(webhook_secret),
        )
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


class PaymentAccountRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_user(self, user_id: uuid.UUID) -> PaymentAccount | None:
        return self.db.scalar(
            select(PaymentAccount).where(PaymentAccount.user_id == user_id)
        )

    def create(
        self,
        user_id: uuid.UUID,
        *,
        account_name: str,
        account_email: str,
        business_type: BusinessType,
        business_name: str,
        branch_ifsc_code: str,
        account_number: str,
        beneficiary_name: str,
    ) -> PaymentAccount:
        account = PaymentAccount(
            user_id=user_id,
            account_name=account_name,
            account_email=account_email,
            business_type=business_type,
            business_name=business_name,
            branch_ifsc_code=branch_ifsc_code,
            encrypted_account_number=encrypt_secret(account_number),
            beneficiary_name=beneficiary_name,
        )
        self.db.add(account)
        self.db.flush()
        return account

    @staticmethod
    def update(
        account: PaymentAccount,
        *,
        account_name: str,
        account_email: str,
        business_type: BusinessType,
        business_name: str,
        branch_ifsc_code: str,
        account_number: str | None,
        beneficiary_name: str,
    ) -> PaymentAccount:
        account.account_name = account_name
        account.account_email = account_email
        account.business_type = business_type
        account.business_name = business_name
        account.branch_ifsc_code = branch_ifsc_code
        account.beneficiary_name = beneficiary_name
        if account_number:
            account.encrypted_account_number = encrypt_secret(account_number)
        return account

    @staticmethod
    def account_number(account: PaymentAccount) -> str:
        return decrypt_secret(account.encrypted_account_number)
