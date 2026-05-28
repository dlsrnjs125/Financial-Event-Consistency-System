"""Integration tests for transaction event HMAC security."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import import_all_models
from app.models.account import Account
from app.models.idempotency_record import IdempotencyRecord
from app.models.ledger_entry import LedgerEntry
from app.models.transaction_event import TransactionEvent
from app.security.hmac import (
    build_signature_base_string,
    generate_body_hash,
    generate_hmac_signature,
)

import_all_models()

SECRET = "test-secret"
CLIENT_ID = "bank-a"
PATH = "/api/v1/transaction-events"


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
def client(db_session, monkeypatch):
    monkeypatch.setattr(settings, "hmac_enabled", True)
    monkeypatch.setattr(settings, "hmac_allowed_skew_seconds", 300)
    monkeypatch.setattr(settings, "external_client_secrets", f"{CLIENT_ID}:{SECRET}")
    monkeypatch.setattr(settings, "redis_enabled", False)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()


def seed_account(db_session, balance=10000):
    account = Account(account_no="1234567890", balance=balance, status="ACTIVE")
    db_session.add(account)
    db_session.commit()
    return account


def payload(external_event_id="ext-sec-001", amount=1000):
    return {
        "external_event_id": external_event_id,
        "account_no": "1234567890",
        "event_type": "DEPOSIT",
        "amount": amount,
        "currency": "KRW",
        "occurred_at": datetime(2026, 5, 28, 10, 0, tzinfo=UTC).isoformat(),
    }


def signed_headers(
    raw_body: bytes,
    timestamp: str | None = None,
    client_id: str = CLIENT_ID,
    secret: str = SECRET,
):
    timestamp = timestamp or datetime.now(UTC).isoformat()
    base_string = build_signature_base_string(
        method="POST",
        path=PATH,
        timestamp=timestamp,
        body_hash=generate_body_hash(raw_body),
    )
    return {
        "Content-Type": "application/json",
        "Idempotency-Key": "idem-sec-001",
        "X-Client-Id": client_id,
        "X-Timestamp": timestamp,
        "X-Signature": generate_hmac_signature(secret, base_string),
    }


def encode_body(body: dict) -> bytes:
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def post_signed(client, body, headers=None):
    raw_body = encode_body(body)
    request_headers = signed_headers(raw_body)
    if headers:
        request_headers.update(headers)
    return client.post(PATH, content=raw_body, headers=request_headers)


def assert_no_financial_rows(db_session):
    assert db_session.query(TransactionEvent).count() == 0
    assert db_session.query(LedgerEntry).count() == 0
    assert db_session.query(IdempotencyRecord).count() == 0


def test_valid_hmac_allows_transaction_event_processing(client, db_session):
    seed_account(db_session)

    response = post_signed(client, payload())

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert db_session.query(TransactionEvent).count() == 1
    assert db_session.query(LedgerEntry).count() == 1
    assert db_session.query(IdempotencyRecord).count() == 1


@pytest.mark.parametrize("header_name", ["X-Client-Id", "X-Timestamp", "X-Signature"])
def test_missing_security_header_returns_400(client, db_session, header_name):
    seed_account(db_session)
    raw_body = encode_body(payload())
    headers = signed_headers(raw_body)
    headers.pop(header_name)

    response = client.post(PATH, content=raw_body, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MISSING_SECURITY_HEADER"
    assert_no_financial_rows(db_session)


def test_unknown_client_returns_403(client, db_session):
    seed_account(db_session)

    response = post_signed(client, payload(), headers={"X-Client-Id": "unknown-client"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNKNOWN_CLIENT"
    assert_no_financial_rows(db_session)


def test_invalid_signature_returns_401(client, db_session):
    seed_account(db_session)

    response = post_signed(client, payload(), headers={"X-Signature": "a" * 64})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_SIGNATURE"
    assert_no_financial_rows(db_session)


def test_expired_timestamp_returns_401(client, db_session):
    seed_account(db_session)
    expired = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    raw_body = encode_body(payload())
    headers = signed_headers(raw_body, timestamp=expired)

    response = client.post(PATH, content=raw_body, headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "EXPIRED_TIMESTAMP"
    assert_no_financial_rows(db_session)


def test_future_timestamp_outside_window_returns_401(client, db_session):
    seed_account(db_session)
    future = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    raw_body = encode_body(payload())
    headers = signed_headers(raw_body, timestamp=future)

    response = client.post(PATH, content=raw_body, headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "EXPIRED_TIMESTAMP"
    assert_no_financial_rows(db_session)


def test_body_tampering_after_signature_returns_401(client, db_session):
    seed_account(db_session)
    signed_body = payload(amount=1000)
    tampered_body = payload(amount=2000)
    headers = signed_headers(encode_body(signed_body))

    response = client.post(PATH, content=encode_body(tampered_body), headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_SIGNATURE"
    assert_no_financial_rows(db_session)


def test_hmac_cannot_be_disabled_in_production(client, db_session, monkeypatch):
    seed_account(db_session)
    monkeypatch.setattr(settings, "hmac_enabled", False)
    monkeypatch.setattr(settings, "app_env", "production")

    response = post_signed(client, payload())

    assert response.status_code == 500
    assert_no_financial_rows(db_session)
