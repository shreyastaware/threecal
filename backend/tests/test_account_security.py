import uuid
from collections.abc import Generator, Sequence
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.domains.auth import router as auth_router
from app.domains.auth.models import AuthToken
from app.domains.bookings.models import Booking, BookingStatus
from app.domains.email.providers import EmailAttachment, EmailProvider
from app.domains.event_types.models import EventType
from app.domains.users.models import User
from app.domains.users.storage import get_object_storage


REGISTER_PAYLOAD = {
    "full_name": "Avery Stone",
    "email": "avery@example.com",
    "password": "strong-password",
}
COOKIE = "threecal_access_token"


class RecordingEmailProvider(EmailProvider):
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    def send(
        self,
        *,
        recipient: str,
        subject: str,
        text: str,
        html: str | None = None,
        attachments: Sequence[EmailAttachment] = (),
    ) -> None:
        self.sent.append({"recipient": recipient, "subject": subject, "text": text, "html": html or ""})

    def last_token(self) -> str:
        link = next(word for word in reversed(self.sent[-1]["text"].split()) if word.startswith("http"))
        return parse_qs(urlparse(link).query)["token"][0]


class FakeObjectStorage:
    public_base_url = "https://assets.threecal.test"

    def __init__(self) -> None:
        self.deleted: list[str] = []

    def upload(self, key: str, content: bytes, content_type: str) -> str:
        return f"{self.public_base_url}/{key}"

    def delete(self, key: str) -> None:
        self.deleted.append(key)

    def key_from_public_url(self, public_url: str) -> str | None:
        prefix = f"{self.public_base_url}/"
        return public_url.removeprefix(prefix) if public_url.startswith(prefix) else None


@pytest.fixture
def emails(monkeypatch: pytest.MonkeyPatch) -> RecordingEmailProvider:
    provider = RecordingEmailProvider()
    monkeypatch.setattr(auth_router, "get_email_provider", lambda: provider)
    return provider


@pytest.fixture
def storage(client: TestClient) -> FakeObjectStorage:
    fake = FakeObjectStorage()
    client.app.dependency_overrides[get_object_storage] = lambda: fake  # type: ignore[attr-defined]
    return fake


@pytest.fixture
def db(client: TestClient) -> Generator[Session, None, None]:
    sessions = client.app.dependency_overrides[get_db]()  # type: ignore[attr-defined]
    yield next(sessions)
    sessions.close()


def register(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201


# --- Email verification -------------------------------------------------------


def test_register_sends_verification_email_and_token_verifies(
    client: TestClient, emails: RecordingEmailProvider, db: Session
) -> None:
    register(client)

    assert client.get("/api/v1/users/me").json()["is_email_verified"] is False
    assert len(emails.sent) == 1
    assert emails.sent[0]["recipient"] == "avery@example.com"
    assert f"{settings.frontend_url}/verify-email?token=" in emails.sent[0]["text"]
    token = emails.last_token()
    # Only the hash is persisted.
    assert db.scalar(select(func.count()).select_from(AuthToken).where(AuthToken.token_hash == token)) == 0

    verified = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verified.status_code == 200
    assert verified.json()["is_email_verified"] is True
    assert client.get("/api/v1/users/me").json()["is_email_verified"] is True

    reused = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert reused.status_code == 400
    assert reused.json()["code"] == "invalid_token"


def test_resend_verification_invalidates_previous_link(client: TestClient, emails: RecordingEmailProvider) -> None:
    register(client)
    first_token = emails.last_token()

    resend = client.post("/api/v1/auth/resend-verification")
    assert resend.status_code == 202
    assert len(emails.sent) == 2
    second_token = emails.last_token()
    assert second_token != first_token

    assert client.post("/api/v1/auth/verify-email", json={"token": first_token}).status_code == 400
    assert client.post("/api/v1/auth/verify-email", json={"token": second_token}).status_code == 200

    already = client.post("/api/v1/auth/resend-verification")
    assert already.status_code == 409
    assert already.json()["code"] == "email_already_verified"


def test_resend_verification_requires_authentication(client: TestClient) -> None:
    assert client.post("/api/v1/auth/resend-verification").status_code == 401


def test_expired_verification_token_is_rejected(
    client: TestClient, emails: RecordingEmailProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_verification_token_ttl_hours", 0)
    register(client)

    response = client.post("/api/v1/auth/verify-email", json={"token": emails.last_token()})
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_token"


def test_unknown_verification_token_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/auth/verify-email", json={"token": "not-a-real-token"})
    assert response.status_code == 400


# --- Password reset -----------------------------------------------------------


def test_forgot_password_does_not_reveal_unknown_accounts(client: TestClient, emails: RecordingEmailProvider) -> None:
    response = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert response.status_code == 202
    assert emails.sent == []


def test_password_reset_flow_revokes_existing_sessions(client: TestClient, emails: RecordingEmailProvider) -> None:
    register(client)
    old_cookie = client.cookies.get(COOKIE)
    assert old_cookie

    forgot = client.post("/api/v1/auth/forgot-password", json={"email": "AVERY@example.com"})
    assert forgot.status_code == 202
    assert emails.sent[-1]["subject"] == "Reset your threecal password"
    assert f"{settings.frontend_url}/reset-password?token=" in emails.sent[-1]["text"]
    first_token = emails.last_token()

    client.post("/api/v1/auth/forgot-password", json={"email": "avery@example.com"})
    token = emails.last_token()
    # Requesting a new link retires the previous one.
    stale = client.post("/api/v1/auth/reset-password", json={"token": first_token, "new_password": "another-password"})
    assert stale.status_code == 400

    reset = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "brand-new-password"})
    assert reset.status_code == 204

    client.cookies.clear()
    client.cookies.set(COOKIE, old_cookie)
    assert client.get("/api/v1/users/me").status_code == 401

    old_login = client.post("/api/v1/auth/login", json={"email": "avery@example.com", "password": "strong-password"})
    assert old_login.status_code == 401
    new_login = client.post("/api/v1/auth/login", json={"email": "avery@example.com", "password": "brand-new-password"})
    assert new_login.status_code == 200
    assert new_login.json()["user"]["is_email_verified"] is True

    reused = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "third-password"})
    assert reused.status_code == 400


def test_reset_password_enforces_password_rules(client: TestClient, emails: RecordingEmailProvider) -> None:
    register(client)
    client.post("/api/v1/auth/forgot-password", json={"email": "avery@example.com"})

    response = client.post("/api/v1/auth/reset-password", json={"token": emails.last_token(), "new_password": "short"})
    assert response.status_code == 422


def test_expired_reset_token_is_rejected(
    client: TestClient, emails: RecordingEmailProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    register(client)
    monkeypatch.setattr(settings, "password_reset_token_ttl_minutes", 0)
    client.post("/api/v1/auth/forgot-password", json={"email": "avery@example.com"})

    response = client.post(
        "/api/v1/auth/reset-password", json={"token": emails.last_token(), "new_password": "brand-new-password"}
    )
    assert response.status_code == 400


# --- Change password ----------------------------------------------------------


def test_change_password_keeps_current_session_and_revokes_others(client: TestClient, storage: FakeObjectStorage) -> None:
    register(client)
    old_cookie = client.cookies.get(COOKIE)
    assert old_cookie

    wrong = client.post(
        "/api/v1/users/me/password",
        json={"current_password": "not-my-password", "new_password": "brand-new-password"},
    )
    assert wrong.status_code == 400
    assert wrong.json()["code"] == "invalid_password"

    changed = client.post(
        "/api/v1/users/me/password",
        json={"current_password": "strong-password", "new_password": "brand-new-password"},
    )
    assert changed.status_code == 200
    new_cookie = client.cookies.get(COOKIE)
    assert new_cookie and new_cookie != old_cookie
    assert client.get("/api/v1/users/me").status_code == 200

    client.cookies.clear()
    client.cookies.set(COOKIE, old_cookie)
    assert client.get("/api/v1/users/me").status_code == 401

    login = client.post("/api/v1/auth/login", json={"email": "avery@example.com", "password": "brand-new-password"})
    assert login.status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"current_password": "strong-password", "new_password": "short"},
        {"current_password": "strong-password", "new_password": "x" * 129},
        {"current_password": "strong-password", "new_password": "strong-password"},
    ],
)
def test_change_password_validates_new_password(
    client: TestClient, storage: FakeObjectStorage, payload: dict[str, str]
) -> None:
    register(client)
    assert client.post("/api/v1/users/me/password", json=payload).status_code == 422


def test_change_password_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/users/me/password",
        json={"current_password": "strong-password", "new_password": "brand-new-password"},
    )
    assert response.status_code == 401


# --- Delete account -----------------------------------------------------------


def _add_booking(db: Session, user_id: uuid.UUID, starts_in: timedelta, status: BookingStatus) -> None:
    event = db.scalars(select(EventType).where(EventType.user_id == user_id)).first()
    assert event
    starts_at = datetime.now(timezone.utc) + starts_in
    db.add(
        Booking(
            host_id=user_id, event_type_id=event.id, invitee_name="Invitee", invitee_email="i@example.com",
            invitee_timezone="UTC", starts_at=starts_at, ends_at=starts_at + timedelta(minutes=30), status=status,
            booking_amount=0, payment_expires_at=starts_at,
        )
    )
    db.commit()


def test_delete_account_requires_correct_password(client: TestClient, storage: FakeObjectStorage) -> None:
    register(client)
    response = client.request("DELETE", "/api/v1/users/me", json={"password": "wrong-password"})
    assert response.status_code == 400
    assert client.get("/api/v1/users/me").status_code == 200


def test_delete_account_blocked_by_upcoming_confirmed_bookings(
    client: TestClient, storage: FakeObjectStorage, db: Session
) -> None:
    register(client)
    user_id = uuid.UUID(client.get("/api/v1/users/me").json()["id"])
    _add_booking(db, user_id, timedelta(days=3), BookingStatus.CONFIRMED)

    response = client.request("DELETE", "/api/v1/users/me", json={"password": "strong-password"})
    assert response.status_code == 409
    assert response.json()["code"] == "upcoming_bookings"
    assert "cancel them first" in response.json()["detail"].lower()


def test_delete_account_removes_user_data_avatar_and_cookie(
    client: TestClient, storage: FakeObjectStorage, db: Session, emails: RecordingEmailProvider
) -> None:
    register(client)
    me = client.get("/api/v1/users/me").json()
    user_id = uuid.UUID(me["id"])
    user = db.get(User, user_id)
    assert user
    user.avatar_url = f"{storage.public_base_url}/profile-pictures/{user_id}/avatar.webp"
    db.commit()
    # Past confirmed and future cancelled bookings do not block deletion.
    _add_booking(db, user_id, timedelta(days=-3), BookingStatus.CONFIRMED)
    _add_booking(db, user_id, timedelta(days=3), BookingStatus.CANCELLED)

    response = client.request("DELETE", "/api/v1/users/me", json={"password": "strong-password"})
    assert response.status_code == 204
    assert storage.deleted == [f"profile-pictures/{user_id}/avatar.webp"]
    assert client.cookies.get(COOKIE) is None
    assert client.get("/api/v1/users/me").status_code == 401

    db.expire_all()
    assert db.get(User, user_id) is None
    for model, column in ((Booking, Booking.host_id), (EventType, EventType.user_id), (AuthToken, AuthToken.user_id)):
        assert db.scalar(select(func.count()).select_from(model).where(column == user_id)) == 0

    login = client.post("/api/v1/auth/login", json={"email": "avery@example.com", "password": "strong-password"})
    assert login.status_code == 401
    # The email can be used for a fresh account.
    register(client)


def test_legacy_token_without_version_claim_is_accepted(client: TestClient) -> None:
    from jose import jwt  # type: ignore[import-untyped]

    register(client)
    user_id = client.get("/api/v1/users/me").json()["id"]
    now = datetime.now(timezone.utc)
    legacy = jwt.encode(
        {"sub": user_id, "type": "access", "iat": now, "exp": now + timedelta(minutes=5)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    client.cookies.clear()
    client.cookies.set(COOKIE, legacy)
    assert client.get("/api/v1/users/me").status_code == 200
