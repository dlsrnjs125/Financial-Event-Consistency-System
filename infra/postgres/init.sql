-- Initialize database schema for the local Docker Compose environment.
-- Keep this file aligned with backend/migrations/versions/0001_initial_schema.py.

CREATE TABLE IF NOT EXISTS accounts (
    id BIGSERIAL PRIMARY KEY,
    account_no VARCHAR(64) UNIQUE NOT NULL,
    balance BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transaction_events (
    id BIGSERIAL PRIMARY KEY,
    external_event_id VARCHAR(128) UNIQUE NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    account_id BIGINT NOT NULL,
    event_type VARCHAR(20) NOT NULL,
    amount BIGINT NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'KRW',
    status VARCHAR(30) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS ledger_entries (
    id BIGSERIAL PRIMARY KEY,
    transaction_event_id BIGINT UNIQUE NOT NULL,
    account_id BIGINT NOT NULL,
    entry_type VARCHAR(20) NOT NULL,
    amount BIGINT NOT NULL,
    balance_after BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_event_id) REFERENCES transaction_events(id),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    id BIGSERIAL PRIMARY KEY,
    idempotency_key VARCHAR(128) UNIQUE NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    status VARCHAR(30) NOT NULL,
    response_code INTEGER,
    response_body JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    locked_until TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS event_state_histories (
    id BIGSERIAL PRIMARY KEY,
    transaction_event_id BIGINT NOT NULL,
    old_status VARCHAR(30),
    new_status VARCHAR(30) NOT NULL,
    reason VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_event_id) REFERENCES transaction_events(id)
);

CREATE INDEX IF NOT EXISTS ix_transaction_events_account_id
    ON transaction_events(account_id);
CREATE INDEX IF NOT EXISTS ix_transaction_events_idempotency_key
    ON transaction_events(idempotency_key);
CREATE INDEX IF NOT EXISTS ix_transaction_events_status
    ON transaction_events(status);
CREATE INDEX IF NOT EXISTS ix_transaction_events_occurred_at
    ON transaction_events(occurred_at);
CREATE INDEX IF NOT EXISTS ix_ledger_entries_account_id
    ON ledger_entries(account_id);
CREATE INDEX IF NOT EXISTS ix_ledger_entries_created_at
    ON ledger_entries(created_at);
CREATE INDEX IF NOT EXISTS ix_idempotency_records_status
    ON idempotency_records(status);
CREATE INDEX IF NOT EXISTS ix_idempotency_records_locked_until
    ON idempotency_records(locked_until);
CREATE INDEX IF NOT EXISTS ix_idempotency_records_expires_at
    ON idempotency_records(expires_at);
CREATE INDEX IF NOT EXISTS ix_event_state_histories_transaction_event_id
    ON event_state_histories(transaction_event_id);
CREATE INDEX IF NOT EXISTS ix_event_state_histories_created_at
    ON event_state_histories(created_at);

INSERT INTO accounts (account_no, balance, status)
VALUES ('ACC-001', 100000, 'ACTIVE')
ON CONFLICT (account_no) DO NOTHING;

INSERT INTO accounts (account_no, balance, status)
VALUES ('ACC-002', 50000, 'ACTIVE')
ON CONFLICT (account_no) DO NOTHING;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
