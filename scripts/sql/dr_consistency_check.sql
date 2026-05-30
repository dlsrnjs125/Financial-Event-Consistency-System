-- Ops Phase 4 PostgreSQL restore consistency checks.
-- This file must be executed against the restore DB, never the source DB.
-- It returns count-only evidence and does not expose row data.

WITH latest_ledger AS (
    SELECT DISTINCT ON (account_id)
        account_id,
        balance_after
    FROM ledger_entries
    ORDER BY account_id, created_at DESC, id DESC
),
sequence_positions AS (
    SELECT
        table_name,
        sequence_name,
        max_id,
        COALESCE(ps.last_value, 0) AS sequence_last_value
    FROM (
        VALUES
            ('accounts', 'accounts_id_seq', (SELECT COALESCE(MAX(id), 0) FROM accounts)),
            ('transaction_events', 'transaction_events_id_seq', (SELECT COALESCE(MAX(id), 0) FROM transaction_events)),
            ('ledger_entries', 'ledger_entries_id_seq', (SELECT COALESCE(MAX(id), 0) FROM ledger_entries)),
            ('idempotency_records', 'idempotency_records_id_seq', (SELECT COALESCE(MAX(id), 0) FROM idempotency_records)),
            ('event_state_histories', 'event_state_histories_id_seq', (SELECT COALESCE(MAX(id), 0) FROM event_state_histories))
    ) AS expected_sequences(table_name, sequence_name, max_id)
    LEFT JOIN pg_sequences ps
        ON ps.schemaname = 'public'
       AND ps.sequencename = expected_sequences.sequence_name
),
checks AS (
    SELECT
        'duplicated_external_event_count' AS check_name,
        COUNT(*)::bigint AS check_value
    FROM (
        SELECT external_event_id
        FROM transaction_events
        GROUP BY external_event_id
        HAVING COUNT(*) > 1
    ) duplicated_external_events

    UNION ALL

    SELECT
        'duplicated_ledger_event_count' AS check_name,
        COUNT(*)::bigint AS check_value
    FROM (
        SELECT transaction_event_id
        FROM ledger_entries
        GROUP BY transaction_event_id
        HAVING COUNT(*) > 1
    ) duplicated_ledger_events

    UNION ALL

    SELECT
        'orphan_ledger_count' AS check_name,
        COUNT(*)::bigint AS check_value
    FROM ledger_entries le
    LEFT JOIN transaction_events te ON te.id = le.transaction_event_id
    WHERE te.id IS NULL

    UNION ALL

    SELECT
        'completed_event_without_ledger_count' AS check_name,
        COUNT(*)::bigint AS check_value
    FROM transaction_events te
    LEFT JOIN ledger_entries le ON le.transaction_event_id = te.id
    WHERE te.status IN ('COMPLETED', 'SETTLED')
      AND le.id IS NULL

    UNION ALL

    SELECT
        'ledger_account_mismatch_count' AS check_name,
        COUNT(*)::bigint AS check_value
    FROM ledger_entries le
    JOIN transaction_events te ON te.id = le.transaction_event_id
    WHERE le.account_id <> te.account_id

    UNION ALL

    SELECT
        'duplicated_idempotency_key_count' AS check_name,
        COUNT(*)::bigint AS check_value
    FROM (
        SELECT idempotency_key
        FROM idempotency_records
        GROUP BY idempotency_key
        HAVING COUNT(*) > 1
    ) duplicated_idempotency_keys

    UNION ALL

    SELECT
        'account_balance_mismatch_count' AS check_name,
        COUNT(*)::bigint AS check_value
    FROM accounts a
    JOIN latest_ledger ll ON ll.account_id = a.id
    WHERE a.balance <> ll.balance_after

    UNION ALL

    SELECT
        'sequence_position_lag_count' AS check_name,
        COUNT(*)::bigint AS check_value
    FROM sequence_positions
    WHERE sequence_last_value < max_id
)
SELECT check_name, check_value
FROM checks
ORDER BY check_name;
