from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core import database
from app.core.database import Base, get_db
from app.main import app
from app.core.rate_limit import get_rate_limit_backend


@pytest.fixture(autouse=True)
def disable_rate_limiting(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    # Suites register and log in repeatedly; rate-limit tests re-enable it explicitly.
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    get_rate_limit_backend().reset()
    yield
    get_rate_limit_backend().reset()


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    auto_create_tables = settings.auto_create_tables
    settings.auto_create_tables = False
    # Event handlers and jobs open their own sessions through database.SessionLocal.
    session_local = database.SessionLocal
    database.SessionLocal = testing_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        database.SessionLocal = session_local
        settings.auto_create_tables = auto_create_tables
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def console_email_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    # Never reach a real SMTP server from tests, whatever the local .env says.
    monkeypatch.setattr(settings, "email_provider", "console")


@pytest.fixture(autouse=True)
def inline_domain_events() -> Generator[None, None, None]:
    # Run event handlers synchronously so tests can assert on their effects.
    from app.core.events import InlineDispatcher, event_bus

    dispatcher = event_bus.dispatcher
    event_bus.dispatcher = InlineDispatcher()
    try:
        yield
    finally:
        event_bus.dispatcher = dispatcher
