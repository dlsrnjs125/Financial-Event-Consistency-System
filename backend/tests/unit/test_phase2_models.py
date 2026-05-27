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


def test_transaction_events_model_matches_data_model_spec():
    events = table("transaction_events")

    assert events.c.external_event_id.type.length == 128
    assert "external_event_id" in unique_column_names(events)
    assert events.c.idempotency_key.type.length == 128
    assert events.c.event_type.type.length == 20
    assert isinstance(events.c.amount.type, BigInteger)
    assert events.c.status.type.length == 30
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
    assert "ix_ledger_entries_account_id" in index_names(ledger_entries)


def test_idempotency_records_model_matches_data_model_spec():
    idempotency_records = table("idempotency_records")

    assert idempotency_records.c.idempotency_key.type.length == 128
    assert "idempotency_key" in unique_column_names(idempotency_records)
    assert idempotency_records.c.request_hash.type.length == 64
    assert idempotency_records.c.status.type.length == 30
    assert isinstance(idempotency_records.c.response_body.type, JSONB)
    assert "expires_at" in idempotency_records.c


def test_event_state_histories_model_matches_data_model_spec():
    histories = table("event_state_histories")

    assert histories.c.transaction_event_id.foreign_keys
    assert histories.c.old_status.nullable is True
    assert histories.c.old_status.type.length == 30
    assert histories.c.new_status.nullable is False
    assert histories.c.new_status.type.length == 30
    assert histories.c.reason.type.length == 255
    assert "ix_event_state_histories_transaction_event_id" in index_names(histories)
