"""Phase 2 SQLAlchemy model metadata tests."""

from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def table(name):
    return Base.metadata.tables[name]


def unique_column_names(model_table):
    unique_names = {column.name for column in model_table.columns if column.unique}
    for constraint in model_table.constraints:
        if constraint.__class__.__name__ == "UniqueConstraint":
            unique_names.update(column.name for column in constraint.columns)
    return unique_names


def index_names(model_table):
    return {index.name for index in model_table.indexes}


def assert_timezone_aware(column):
    assert column.type.timezone is True


def test_base_metadata_uses_stable_naming_convention():
    assert {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }.items() <= Base.metadata.naming_convention.items()


def test_phase2_tables_are_registered_for_alembic_metadata():
    assert {
        "accounts",
        "transaction_events",
        "ledger_entries",
        "idempotency_records",
        "event_state_histories",
    }.issubset(Base.metadata.tables)


def test_accounts_model_matches_data_model_spec():
    accounts = table("accounts")

    assert isinstance(accounts.c.id.type, BigInteger)
    assert isinstance(accounts.c.account_no.type, String)
    assert accounts.c.account_no.type.length == 64
    assert accounts.c.account_no.nullable is False
    assert "account_no" in unique_column_names(accounts)
    assert isinstance(accounts.c.balance.type, BigInteger)
    assert accounts.c.status.type.length == 20
    assert accounts.c.status.server_default.arg == "ACTIVE"
    assert_timezone_aware(accounts.c.created_at)
    assert_timezone_aware(accounts.c.updated_at)


def test_transaction_events_model_matches_data_model_spec():
    events = table("transaction_events")

    assert events.c.external_event_id.type.length == 128
    assert "external_event_id" in unique_column_names(events)
    assert events.c.idempotency_key.type.length == 128
    assert events.c.event_type.type.length == 20
    assert isinstance(events.c.amount.type, BigInteger)
    assert events.c.currency.type.length == 10
    assert events.c.currency.server_default.arg == "KRW"
    assert events.c.status.type.length == 30
    assert "updated_at" in events.c
    assert_timezone_aware(events.c.occurred_at)
    assert_timezone_aware(events.c.created_at)
    assert_timezone_aware(events.c.updated_at)
    assert events.c.account_id.foreign_keys
    assert "ix_transaction_events_account_id" in index_names(events)
    assert "ix_transaction_events_status" in index_names(events)


def test_ledger_entries_model_matches_data_model_spec():
    ledger_entries = table("ledger_entries")

    assert "transaction_event_id" in unique_column_names(ledger_entries)
    assert ledger_entries.c.transaction_event_id.foreign_keys
    assert ledger_entries.c.account_id.foreign_keys
    assert ledger_entries.c.entry_type.type.length == 20
    assert isinstance(ledger_entries.c.amount.type, BigInteger)
    assert isinstance(ledger_entries.c.balance_after.type, BigInteger)
    assert_timezone_aware(ledger_entries.c.created_at)
    assert "ix_ledger_entries_account_id" in index_names(ledger_entries)


def test_idempotency_records_model_matches_data_model_spec():
    idempotency_records = table("idempotency_records")

    assert idempotency_records.c.idempotency_key.type.length == 128
    assert "idempotency_key" in unique_column_names(idempotency_records)
    assert idempotency_records.c.request_hash.type.length == 64
    assert idempotency_records.c.status.type.length == 30
    assert isinstance(idempotency_records.c.response_body.type, JSONB)
    assert "updated_at" in idempotency_records.c
    assert "locked_until" in idempotency_records.c
    assert "expires_at" in idempotency_records.c
    assert_timezone_aware(idempotency_records.c.created_at)
    assert_timezone_aware(idempotency_records.c.updated_at)
    assert_timezone_aware(idempotency_records.c.completed_at)
    assert_timezone_aware(idempotency_records.c.locked_until)
    assert_timezone_aware(idempotency_records.c.expires_at)
    assert "ix_idempotency_records_locked_until" in index_names(idempotency_records)


def test_event_state_histories_model_matches_data_model_spec():
    histories = table("event_state_histories")

    assert histories.c.transaction_event_id.foreign_keys
    assert histories.c.old_status.nullable is True
    assert histories.c.old_status.type.length == 30
    assert histories.c.new_status.nullable is False
    assert histories.c.new_status.type.length == 30
    assert histories.c.reason.type.length == 255
    assert_timezone_aware(histories.c.created_at)
    assert "ix_event_state_histories_transaction_event_id" in index_names(histories)
