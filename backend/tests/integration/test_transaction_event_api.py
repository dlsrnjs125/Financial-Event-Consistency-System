"""Integration tests for transaction event API endpoints."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import import_all_models
from app.models.account import Account
from app.services.write_suspension_service import (
    get_write_suspension_service,
    reset_write_suspension_service_for_testing,
)

import_all_models()


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(db_session, monkeypatch, tmp_path):
    # These tests cover Phase 5/6 transaction consistency behavior. Phase 7 HMAC
    # enforcement is covered separately in test_transaction_event_security.py.
    monkeypatch.setattr(settings, "hmac_enabled", False)
    monkeypatch.setattr(settings, "redis_enabled", False)
    monkeypatch.setattr(settings, "redis_lock_enabled", False)
    monkeypatch.setattr(settings, "idempotency_cache_enabled", False)
    monkeypatch.setattr(
        settings,
        "write_suspend_state_file",
        str(tmp_path / "write-suspend-state.json"),
    )
    reset_write_suspension_service_for_testing()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        reset_write_suspension_service_for_testing()


def seed_account(db_session, balance=10000):
    account = Account(account_no="1234567890", balance=balance, status="ACTIVE")
    db_session.add(account)
    db_session.commit()
    return account


def payload(external_event_id="ext-001", amount=1000):
    return {
        "external_event_id": external_event_id,
        "account_no": "1234567890",
        "event_type": "DEPOSIT",
        "amount": amount,
        "currency": "KRW",
        "occurred_at": datetime(2026, 5, 28, 10, 0, tzinfo=UTC).isoformat(),
    }


def test_post_transaction_event_deposit_returns_200(client, db_session):
    seed_account(db_session)

    response = client.post(
        "/api/v1/transaction-events",
        json=payload(),
        headers={"Idempotency-Key": "idem-001"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["balance_after"] == 11000


def test_post_transaction_event_requires_idempotency_key(client, db_session):
    seed_account(db_session)

    response = client.post("/api/v1/transaction-events", json=payload())

    assert response.status_code == 400


def test_same_key_same_body_replays_response(client, db_session):
    seed_account(db_session)

    first = client.post(
        "/api/v1/transaction-events",
        json=payload(),
        headers={"Idempotency-Key": "idem-001"},
    )
    second = client.post(
        "/api/v1/transaction-events",
        json=payload(),
        headers={"Idempotency-Key": "idem-001"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_same_key_different_body_returns_409(client, db_session):
    seed_account(db_session)
    client.post(
        "/api/v1/transaction-events",
        json=payload(),
        headers={"Idempotency-Key": "idem-001"},
    )

    response = client.post(
        "/api/v1/transaction-events",
        json=payload(external_event_id="ext-002", amount=2000),
        headers={"Idempotency-Key": "idem-001"},
    )

    assert response.status_code == 409


def test_get_account_balance_masks_account_no(client, db_session):
    seed_account(db_session, balance=12000)

    response = client.get("/api/v1/accounts/1234567890/balance")

    assert response.status_code == 200
    assert response.json()["account_no"] == "******7890"
    assert response.json()["balance"] == 12000


def test_write_suspend_blocks_transaction_post_with_retry_after(client, db_session):
    seed_account(db_session)
    get_write_suspension_service().enable(
        reason="postgres_unavailable",
        activated_by="test",
        source="test",
        retry_after_seconds=45,
        run_id="test-run",
    )

    response = client.post(
        "/api/v1/transaction-events",
        json=payload(),
        headers={"Idempotency-Key": "idem-001"},
    )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "45"
    assert response.json()["error_code"] == "WRITE_SUSPENDED"
    assert response.json()["retryable"] is True


def test_health_is_not_blocked_when_write_suspend_active(client, db_session):
    get_write_suspension_service().enable(
        reason="postgres_unavailable",
        activated_by="test",
        source="test",
        run_id="test-run",
    )

    response = client.get("/health")

    assert response.status_code == 200


def test_postgres_probe_failure_activates_write_suspend(client):
    class BrokenSession:
        def execute(self, statement):
            raise SQLAlchemyError("postgres unavailable")

        def close(self):
            return None

    def override_get_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = override_get_db

    response = client.post(
        "/api/v1/transaction-events",
        json=payload(),
        headers={"Idempotency-Key": "idem-001"},
    )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
    assert response.json()["error_code"] == "WRITE_SUSPENDED"
    state = get_write_suspension_service().status()
    assert state.active is True
    assert state.reason == "postgres_unavailable"
