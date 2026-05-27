-- Initialize database schema
-- This script is run when PostgreSQL container starts

CREATE TABLE IF NOT EXISTS accounts (
    id BIGSERIAL PRIMARY KEY,
    account_no VARCHAR(255) UNIQUE NOT NULL,
    balance DECIMAL(18,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transaction_events (
    id BIGSERIAL PRIMARY KEY,
    external_event_id VARCHAR(255) UNIQUE NOT NULL,
    account_id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    amount DECIMAL(18,2) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'RECEIVED',
    occurred_at TIMESTAMP NOT NULL,
    received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS ledger_entries (
    id BIGSERIAL PRIMARY KEY,
    transaction_event_id BIGINT UNIQUE NOT NULL,
    account_id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    amount DECIMAL(18,2) NOT NULL,
    balance_after DECIMAL(18,2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_event_id) REFERENCES transaction_events(id),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    id BIGSERIAL PRIMARY KEY,
    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PROCESSING',
    response_body JSONB,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS event_state_histories (
    id BIGSERIAL PRIMARY KEY,
    transaction_event_id BIGINT NOT NULL,
    old_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    reason VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_event_id) REFERENCES transaction_events(id)
);

-- Create indexes
CREATE INDEX idx_transaction_events_account_id ON transaction_events(account_id);
CREATE INDEX idx_transaction_events_status ON transaction_events(status);
CREATE INDEX idx_ledger_entries_account_id ON ledger_entries(account_id);
CREATE INDEX idx_idempotency_key ON idempotency_records(idempotency_key);
CREATE INDEX idx_event_state_histories_event_id ON event_state_histories(transaction_event_id);

-- Insert test account
INSERT INTO accounts (account_no, balance) VALUES ('ACC-001', 100000)
ON CONFLICT (account_no) DO NOTHING;

INSERT INTO accounts (account_no, balance) VALUES ('ACC-002', 50000)
ON CONFLICT (account_no) DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
