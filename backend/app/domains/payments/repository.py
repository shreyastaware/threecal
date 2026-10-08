import json
import uuid
from dataclasses import asdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_secret, encrypt_secret
from app.domains.payments.gateways import LinkedAccountState, PayoutRequirement
from app.domains.payments.models import LinkedAccountStatus, PaymentAccount


class PaymentAccountRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_user(self, user_id: uuid.UUID) -> PaymentAccount | None:
        return self.db.scalar(
            select(PaymentAccount).where(PaymentAccount.user_id == user_id)
        )

    def get_by_linked_account_id(self, linked_account_id: str) -> PaymentAccount | None:
        return self.db.scalar(
            select(PaymentAccount).where(PaymentAccount.linked_account_id == linked_account_id)
        )

    def create(
        self,
        user_id: uuid.UUID,
        *,
        account_number: str,
        pan: str | None,
        **fields: Any,
    ) -> PaymentAccount:
        account = PaymentAccount(
            user_id=user_id,
            encrypted_account_number=encrypt_secret(account_number),
            encrypted_pan=encrypt_secret(pan) if pan else None,
            **fields,
        )
        self.db.add(account)
        self.db.flush()
        return account

    @staticmethod
    def update(
        account: PaymentAccount,
        *,
        account_number: str | None,
        pan: str | None,
        **fields: Any,
    ) -> PaymentAccount:
        for name, value in fields.items():
            setattr(account, name, value)
        if account_number:
            account.encrypted_account_number = encrypt_secret(account_number)
        if pan:
            account.encrypted_pan = encrypt_secret(pan)
        return account

    @staticmethod
    def account_number(account: PaymentAccount) -> str:
        return decrypt_secret(account.encrypted_account_number)

    @staticmethod
    def pan(account: PaymentAccount) -> str | None:
        return decrypt_secret(account.encrypted_pan) if account.encrypted_pan else None

    @staticmethod
    def linked_state(account: PaymentAccount) -> LinkedAccountState:
        return LinkedAccountState(
            linked_account_id=account.linked_account_id,
            stakeholder_id=account.stakeholder_id,
            product_configuration_id=account.product_configuration_id,
            activation_status=account.activation_status or LinkedAccountStatus.NOT_STARTED.value,
            requirements=PaymentAccountRepository.requirements(account),
        )

    @staticmethod
    def apply_linked_state(account: PaymentAccount, state: LinkedAccountState) -> PaymentAccount:
        account.linked_account_id = state.linked_account_id
        account.stakeholder_id = state.stakeholder_id
        account.product_configuration_id = state.product_configuration_id
        account.activation_status = state.activation_status
        PaymentAccountRepository.set_requirements(account, state.requirements)
        return account

    @staticmethod
    def set_requirements(account: PaymentAccount, requirements: list[PayoutRequirement]) -> None:
        account.requirements_json = json.dumps([asdict(item) for item in requirements]) if requirements else None

    @staticmethod
    def requirements(account: PaymentAccount) -> list[PayoutRequirement]:
        if not account.requirements_json:
            return []
        try:
            items = json.loads(account.requirements_json)
        except ValueError:
            return []
        return [PayoutRequirement(**item) for item in items if isinstance(item, dict)]
