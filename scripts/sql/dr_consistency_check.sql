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
)
SELECT check_name, check_value
FROM checks
ORDER BY check_name;
