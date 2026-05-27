"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_no", sa.String(length=64), nullable=False),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="ACTIVE"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("account_no", name="uq_accounts_account_no"),
    )

    op.create_table(
        "transaction_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("external_event_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency", sa.String(length=10), nullable=False, server_default="KRW"
        ),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.UniqueConstraint(
            "external_event_id", name="uq_transaction_events_external_event_id"
        ),
    )
    op.create_index(
        "ix_transaction_events_account_id",
        "transaction_events",
        ["account_id"],
    )
    op.create_index(
        "ix_transaction_events_idempotency_key",
        "transaction_events",
        ["idempotency_key"],
    )
    op.create_index("ix_transaction_events_status", "transaction_events", ["status"])
    op.create_index(
        "ix_transaction_events_occurred_at",
        "transaction_events",
        ["occurred_at"],
    )

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("transaction_event_id", sa.BigInteger(), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("entry_type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["transaction_event_id"], ["transaction_events.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.UniqueConstraint(
            "transaction_event_id", name="uq_ledger_entries_transaction_event_id"
        ),
    )
    op.create_index("ix_ledger_entries_account_id", "ledger_entries", ["account_id"])
    op.create_index("ix_ledger_entries_created_at", "ledger_entries", ["created_at"])

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("response_body", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_idempotency_records_key"),
    )
    op.create_index("ix_idempotency_records_status", "idempotency_records", ["status"])
    op.create_index(
        "ix_idempotency_records_locked_until",
        "idempotency_records",
        ["locked_until"],
    )
    op.create_index(
        "ix_idempotency_records_expires_at",
        "idempotency_records",
        ["expires_at"],
    )

    op.create_table(
        "event_state_histories",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("transaction_event_id", sa.BigInteger(), nullable=False),
        sa.Column("old_status", sa.String(length=30), nullable=True),
        sa.Column("new_status", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["transaction_event_id"], ["transaction_events.id"]),
    )
    op.create_index(
        "ix_event_state_histories_transaction_event_id",
        "event_state_histories",
        ["transaction_event_id"],
    )
    op.create_index(
        "ix_event_state_histories_created_at",
        "event_state_histories",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_event_state_histories_created_at", table_name="event_state_histories"
    )
    op.drop_index(
        "ix_event_state_histories_transaction_event_id",
        table_name="event_state_histories",
    )
    op.drop_table("event_state_histories")
    op.drop_index("ix_idempotency_records_expires_at", table_name="idempotency_records")
    op.drop_index(
        "ix_idempotency_records_locked_until", table_name="idempotency_records"
    )
    op.drop_index("ix_idempotency_records_status", table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index("ix_ledger_entries_created_at", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_account_id", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index("ix_transaction_events_occurred_at", table_name="transaction_events")
    op.drop_index("ix_transaction_events_status", table_name="transaction_events")
    op.drop_index(
        "ix_transaction_events_idempotency_key", table_name="transaction_events"
    )
    op.drop_index("ix_transaction_events_account_id", table_name="transaction_events")
    op.drop_table("transaction_events")
    op.drop_table("accounts")
