"""Unit tests for TransactionEventService decision handling."""

from datetime import UTC, datetime
from types import SimpleNamespace

from app.domain.idempotency import IdempotencyCheckResult, IdempotencyDecision
from app.domain.transaction_status import TransactionStatus
from app.schemas.transaction_event import TransactionEventCreateRequest
from app.services.transaction_event_service import TransactionEventService


class FakeSession:
    def begin(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def rollback(self):
        self.rolled_back = True


class FakeIdempotencyService:
    def __init__(self, decision):
        self.decision = decision
        self.completed = []
        self.failed = []

    def check_or_start(self, idempotency_key, payload):
        return self.decision

    def complete(self, idempotency_key, response_code, response_body, payload=None):
        self.completed.append((idempotency_key, response_code, response_body, payload))

    def fail(
        self,
        idempotency_key,
        response_code=None,
        response_body=None,
        error_message=None,
        payload=None,
    ):
        self.failed.append(
            (idempotency_key, response_code, response_body, error_message, payload)
        )


class FakeTransactionEventRepository:
    def __init__(self):
        self.existing = None
        self.created = None

    def get_by_external_event_id(self, external_event_id):
        return self.existing

    def get_original_for_cancel(self, original_external_event_id):
        return None

    def create_received(self, **kwargs):
        self.created = SimpleNamespace(
            id=1,
            status=TransactionStatus.RECEIVED.value,
            **kwargs,
        )
        return self.created


class FakeAccountRepository:
    def __init__(self, account=None):
        self.account = account

    def get_by_account_no_for_update(self, account_no):
        return self.account


class FakeLedgerService:
    def __init__(self):
        self.ledger = SimpleNamespace(balance_after=11000)
        self.ledger_entry_repository = SimpleNamespace(
            get_by_transaction_event_id=lambda event_id: self.ledger
        )

    def apply_event(self, account, transaction_event, original_event=None):
        return self.ledger


class FakeTransactionStateService:
    def change_status(self, transaction_event, next_status, reason=None):
        transaction_event.status = next_status.value


def make_request(external_event_id="ext-001", amount=1000):
    return TransactionEventCreateRequest(
        external_event_id=external_event_id,
        account_no="1234567890",
        event_type="DEPOSIT",
        amount=amount,
        currency="KRW",
        occurred_at=datetime(2026, 5, 28, 10, 0, tzinfo=UTC),
    )


def make_service(decision, account=None):
    idempotency_service = FakeIdempotencyService(decision)
    event_repository = FakeTransactionEventRepository()
    service = TransactionEventService(
        session=FakeSession(),
        idempotency_service=idempotency_service,
        transaction_event_repository=event_repository,
        account_repository=FakeAccountRepository(account),
        ledger_service=FakeLedgerService(),
        transaction_state_service=FakeTransactionStateService(),
    )
    return service, idempotency_service, event_repository


def test_already_processing_returns_202():
    service, _, _ = make_service(
        IdempotencyCheckResult(IdempotencyDecision.ALREADY_PROCESSING, 1)
    )

    result = service.process("idem-001", make_request())

    assert result.status_code == 202
    assert result.body["status"] == "PROCESSING"


def test_replay_completed_returns_saved_response():
    service, _, _ = make_service(
        IdempotencyCheckResult(
            IdempotencyDecision.REPLAY_COMPLETED,
            1,
            response_code=200,
            response_body={"ok": True},
        )
    )

    result = service.process("idem-001", make_request())

    assert result.status_code == 200
    assert result.body == {"ok": True}


def test_started_processes_transaction_and_completes_idempotency():
    account = SimpleNamespace(id=1, balance=10000)
    service, idempotency_service, _ = make_service(
        IdempotencyCheckResult(IdempotencyDecision.STARTED, 1),
        account,
    )
    request = make_request()

    result = service.process("idem-001", request)

    assert result.status_code == 200
    assert result.body["status"] == "COMPLETED"
    assert idempotency_service.completed
    assert idempotency_service.completed[0][3] == request.model_dump(mode="json")


def test_account_not_found_marks_idempotency_failed():
    service, idempotency_service, _ = make_service(
        IdempotencyCheckResult(IdempotencyDecision.STARTED, 1),
        account=None,
    )

    result = service.process("idem-001", make_request())

    assert result.status_code == 404
    assert result.body["code"] == "AccountNotFound"
    assert idempotency_service.failed


def test_duplicate_external_event_returns_duplicate_response():
    account = SimpleNamespace(id=1, balance=10000)
    service, _, event_repository = make_service(
        IdempotencyCheckResult(IdempotencyDecision.STARTED, 1),
        account,
    )
    event_repository.existing = SimpleNamespace(
        id=10,
        external_event_id="ext-001",
        status=TransactionStatus.COMPLETED.value,
    )

    result = service.process("idem-001", make_request())

    assert result.status_code == 200
    assert result.body["processed"] is False
    assert result.body["duplicated"] is True
