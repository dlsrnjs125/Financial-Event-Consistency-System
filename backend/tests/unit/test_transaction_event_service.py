"""Unit tests for TransactionEventService decision handling."""

from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from app.cache.redis_lock import RedisLockResult
from app.domain.exceptions import TargetQuarantined
from app.domain.idempotency import IdempotencyCheckResult, IdempotencyDecision
from app.domain.recovery import QuarantineTargetType
from app.domain.transaction_status import TransactionStatus
from app.schemas.transaction_event import TransactionEventCreateRequest
from app.services.transaction_event_service import TransactionEventService


class FakeSession:
    def __init__(self):
        self.began = False
        self.rolled_back = False

    def begin(self):
        self.began = True
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


class FlakyIdempotencyService(FakeIdempotencyService):
    def __init__(self):
        super().__init__(
            IdempotencyCheckResult(IdempotencyDecision.ALREADY_PROCESSING, 1)
        )
        self.check_calls = 0

    def check_or_start(self, idempotency_key, payload):
        self.check_calls += 1
        if self.check_calls == 1:
            raise IntegrityError("insert", {}, Exception("unique conflict"))
        return self.decision


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


class FakeRedisLock:
    def __init__(self, result):
        self.result = result
        self.acquired_keys = []
        self.released = []

    def acquire(self, key):
        self.acquired_keys.append(key)
        return self.result

    def release(self, key, token):
        self.released.append((key, token))


class FakeQuarantineService:
    def assert_not_quarantined(self, target_type, target_id):
        assert target_type == QuarantineTargetType.ACCOUNT
        assert target_id == "1"
        raise TargetQuarantined(target_type.value, "qr-test")


def make_request(external_event_id="ext-001", amount=1000):
    return TransactionEventCreateRequest(
        external_event_id=external_event_id,
        account_no="1234567890",
        event_type="DEPOSIT",
        amount=amount,
        currency="KRW",
        occurred_at=datetime(2026, 5, 28, 10, 0, tzinfo=UTC),
    )


def make_service(decision, account=None, redis_lock=None, quarantine_service=None):
    idempotency_service = FakeIdempotencyService(decision)
    event_repository = FakeTransactionEventRepository()
    session = FakeSession()
    service = TransactionEventService(
        session=session,
        idempotency_service=idempotency_service,
        transaction_event_repository=event_repository,
        account_repository=FakeAccountRepository(account),
        ledger_service=FakeLedgerService(),
        transaction_state_service=FakeTransactionStateService(),
        redis_lock=redis_lock,
        quarantine_service=quarantine_service,
    )
    return service, idempotency_service, event_repository, session


def test_already_processing_returns_202():
    service, _, _, _ = make_service(
        IdempotencyCheckResult(IdempotencyDecision.ALREADY_PROCESSING, 1)
    )

    result = service.process("idem-001", make_request())

    assert result.status_code == 202
    assert result.body["status"] == "PROCESSING"


def test_replay_completed_returns_saved_response():
    service, _, _, _ = make_service(
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
    service, idempotency_service, _, _ = make_service(
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
    service, idempotency_service, _, _ = make_service(
        IdempotencyCheckResult(IdempotencyDecision.STARTED, 1),
        account=None,
    )

    result = service.process("idem-001", make_request())

    assert result.status_code == 404
    assert result.body["code"] == "AccountNotFound"
    assert idempotency_service.failed


def test_quarantined_account_marks_idempotency_failed():
    account = SimpleNamespace(id=1, balance=10000)
    service, idempotency_service, _, _ = make_service(
        IdempotencyCheckResult(IdempotencyDecision.STARTED, 1),
        account=account,
        quarantine_service=FakeQuarantineService(),
    )

    result = service.process("idem-001", make_request())

    assert result.status_code == 409
    assert result.body["code"] == "TargetQuarantined"
    assert "1234567890" not in result.body["message"]
    assert idempotency_service.failed


def test_duplicate_external_event_returns_duplicate_response():
    account = SimpleNamespace(id=1, balance=10000)
    service, _, event_repository, _ = make_service(
        IdempotencyCheckResult(IdempotencyDecision.STARTED, 1),
        account,
    )
    event_repository.existing = SimpleNamespace(
        id=10,
        account_id=1,
        external_event_id="ext-001",
        event_type="DEPOSIT",
        amount=1000,
        currency="KRW",
        occurred_at=datetime(2026, 5, 28, 10, 0, tzinfo=UTC),
        status=TransactionStatus.COMPLETED.value,
    )

    result = service.process("idem-001", make_request())

    assert result.status_code == 200
    assert result.body["processed"] is False
    assert result.body["duplicated"] is True


def test_redis_lock_rejected_returns_202_without_db_transaction():
    redis_lock = FakeRedisLock(
        RedisLockResult(
            acquired=False,
            token=None,
            redis_available=True,
            reason="lock_not_acquired",
        )
    )
    service, idempotency_service, _, session = make_service(
        IdempotencyCheckResult(IdempotencyDecision.STARTED, 1),
        account=SimpleNamespace(id=1, balance=10000),
        redis_lock=redis_lock,
    )

    result = service.process("idem-001", make_request())

    assert result.status_code == 202
    assert result.body["status"] == "PROCESSING"
    assert idempotency_service.completed == []
    assert session.began is False
    assert redis_lock.released == []


def test_db_integrity_conflict_rolls_back_and_retries_once():
    idempotency_service = FlakyIdempotencyService()
    session = FakeSession()
    service = TransactionEventService(
        session=session,
        idempotency_service=idempotency_service,
        transaction_event_repository=FakeTransactionEventRepository(),
        account_repository=FakeAccountRepository(SimpleNamespace(id=1, balance=10000)),
        ledger_service=FakeLedgerService(),
        transaction_state_service=FakeTransactionStateService(),
    )

    result = service.process("idem-001", make_request())

    assert result.status_code == 202
    assert result.body["idempotency_key_status"] == "processing"
    assert idempotency_service.check_calls == 2
    assert session.rolled_back is True


def test_redis_lock_acquired_runs_existing_process_and_releases():
    redis_lock = FakeRedisLock(
        RedisLockResult(
            acquired=True,
            token="owner-token",
            redis_available=True,
        )
    )
    service, _, _, session = make_service(
        IdempotencyCheckResult(IdempotencyDecision.STARTED, 1),
        account=SimpleNamespace(id=1, balance=10000),
        redis_lock=redis_lock,
    )

    result = service.process("idem-001", make_request())

    assert result.status_code == 200
    assert session.began is True
    assert redis_lock.released == [
        (redis_lock.acquired_keys[0], "owner-token"),
    ]


def test_redis_unavailable_falls_back_to_db_process():
    redis_lock = FakeRedisLock(
        RedisLockResult(
            acquired=False,
            token=None,
            redis_available=False,
            reason="redis timeout",
        )
    )
    service, idempotency_service, _, session = make_service(
        IdempotencyCheckResult(IdempotencyDecision.STARTED, 1),
        account=SimpleNamespace(id=1, balance=10000),
        redis_lock=redis_lock,
    )

    result = service.process("idem-001", make_request())

    assert result.status_code == 200
    assert session.began is True
    assert idempotency_service.completed
    assert redis_lock.released == []
