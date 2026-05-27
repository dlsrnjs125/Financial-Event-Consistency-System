"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_no", sa.String(length=255), nullable=False, unique=True),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "transaction_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("external_event_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="RECEIVED"),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
    )
    op.create_index(
        "idx_transaction_events_account_id",
        "transaction_events",
        ["account_id"],
    )
    op.create_index("idx_transaction_events_status", "transaction_events", ["status"])

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("transaction_event_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["transaction_event_id"], ["transaction_events.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
    )
    op.create_index("idx_ledger_entries_account_id", "ledger_entries", ["account_id"])

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PROCESSING"),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_idempotency_key", "idempotency_records", ["idempotency_key"])

    op.create_table(
        "event_state_histories",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("transaction_event_id", sa.BigInteger(), nullable=False),
        sa.Column("old_status", sa.String(length=50), nullable=True),
        sa.Column("new_status", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["transaction_event_id"], ["transaction_events.id"]),
    )
    op.create_index(
        "idx_event_state_histories_event_id",
        "event_state_histories",
        ["transaction_event_id"],
    )

    op.execute("INSERT INTO accounts (account_no, balance) VALUES ('ACC-001', 100000)")
    op.execute("INSERT INTO accounts (account_no, balance) VALUES ('ACC-002', 50000)")


def downgrade() -> None:
    op.drop_index("idx_event_state_histories_event_id", table_name="event_state_histories")
    op.drop_table("event_state_histories")
    op.drop_index("idx_idempotency_key", table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index("idx_ledger_entries_account_id", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index("idx_transaction_events_status", table_name="transaction_events")
    op.drop_index("idx_transaction_events_account_id", table_name="transaction_events")
    op.drop_table("transaction_events")
    op.drop_table("accounts")
