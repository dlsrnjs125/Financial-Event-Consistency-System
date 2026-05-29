"""Smoke check PostgreSQL migration constraints used by the CI gate."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text

from app.models import Account, IdempotencyRecord, LedgerEntry, TransactionEvent


EXPECTED_UNIQUE_CONSTRAINTS = {
    "accounts": "uq_accounts_account_no",
    "idempotency_records": "uq_idempotency_records_key",
    "transaction_events": "uq_transaction_events_external_event_id",
    "ledger_entries": "uq_ledger_entries_transaction_event_id",
}


def main() -> None:
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/financial_events",
    )
    engine = create_engine(database_url)

    assert Account.__tablename__ == "accounts"
    assert IdempotencyRecord.__tablename__ == "idempotency_records"
    assert TransactionEvent.__tablename__ == "transaction_events"
    assert LedgerEntry.__tablename__ == "ledger_entries"

    missing_constraints: list[str] = []
    with engine.connect() as connection:
        for table_name, constraint_name in EXPECTED_UNIQUE_CONSTRAINTS.items():
            exists = connection.execute(
                text(
                    """
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    WHERE t.relname = :table_name
                      AND c.conname = :constraint_name
                      AND c.contype = 'u'
                    """
                ),
                {"table_name": table_name, "constraint_name": constraint_name},
            ).scalar_one_or_none()
            if exists != 1:
                missing_constraints.append(constraint_name)

    if missing_constraints:
        formatted = ", ".join(missing_constraints)
        raise AssertionError(f"missing unique constraints: {formatted}")

    print("Migration constraint smoke check passed.")


if __name__ == "__main__":
    main()
