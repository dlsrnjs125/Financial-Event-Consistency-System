"""add recovery case and quarantine tables

Revision ID: 0002_recovery_case_quarantine
Revises: 0001_initial_schema
Create Date: 2026-07-06
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_recovery_case_quarantine"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recovery_cases",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("source_key", sa.String(length=255), nullable=False),
        sa.Column("case_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("current_status", sa.String(length=40), nullable=False),
        sa.Column("classification", sa.String(length=80), nullable=False),
        sa.Column("confidence_candidate", sa.Float(), nullable=True),
        sa.Column("account_id", sa.BigInteger(), nullable=True),
        sa.Column("transaction_event_id", sa.BigInteger(), nullable=True),
        sa.Column("external_event_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True),
        sa.Column("client_id", sa.String(length=64), nullable=True),
        sa.Column("detected_by", sa.String(length=80), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_incident_id", sa.String(length=128), nullable=True),
        sa.Column("source_artifact_path", sa.Text(), nullable=True),
        sa.Column("source_analyzer_result_path", sa.Text(), nullable=True),
        sa.Column("proposed_action", sa.String(length=64), nullable=False),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_reason", sa.Text(), nullable=True),
        sa.Column("executing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_failure_type", sa.String(length=80), nullable=True),
        sa.Column("action_attempt_id", sa.String(length=80), nullable=True),
        sa.Column("evidence_path", sa.Text(), nullable=True),
        sa.Column("before_snapshot_hash", sa.String(length=64), nullable=True),
        sa.Column("after_snapshot_hash", sa.String(length=64), nullable=True),
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
        sa.ForeignKeyConstraint(["transaction_event_id"], ["transaction_events.id"]),
        sa.UniqueConstraint("case_id", name="uq_recovery_cases_case_id"),
        sa.UniqueConstraint("source_key", name="uq_recovery_cases_source_key"),
    )
    op.create_index(
        "ix_recovery_cases_current_status",
        "recovery_cases",
        ["current_status"],
    )
    op.create_index("ix_recovery_cases_case_type", "recovery_cases", ["case_type"])
    op.create_index(
        "ix_recovery_cases_source_incident_id",
        "recovery_cases",
        ["source_incident_id"],
    )

    op.create_table(
        "quarantine_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("quarantine_id", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source_recovery_case_id", sa.BigInteger(), nullable=True),
        sa.Column("source_incident_id", sa.String(length=128), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_by", sa.String(length=128), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by", sa.String(length=128), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["source_recovery_case_id"], ["recovery_cases.id"]),
    )
    op.create_index(
        "ix_quarantine_records_active_target",
        "quarantine_records",
        ["active", "target_type", "target_id"],
    )
    op.create_index(
        "ix_quarantine_records_quarantine_id",
        "quarantine_records",
        ["quarantine_id"],
        unique=True,
    )
    op.create_index(
        "ix_quarantine_records_source_recovery_case_id",
        "quarantine_records",
        ["source_recovery_case_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_quarantine_records_source_recovery_case_id",
        table_name="quarantine_records",
    )
    op.drop_index(
        "ix_quarantine_records_quarantine_id",
        table_name="quarantine_records",
    )
    op.drop_index(
        "ix_quarantine_records_active_target",
        table_name="quarantine_records",
    )
    op.drop_table("quarantine_records")
    op.drop_index("ix_recovery_cases_source_incident_id", table_name="recovery_cases")
    op.drop_index("ix_recovery_cases_case_type", table_name="recovery_cases")
    op.drop_index("ix_recovery_cases_current_status", table_name="recovery_cases")
    op.drop_table("recovery_cases")
