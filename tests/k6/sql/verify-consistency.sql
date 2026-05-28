-- Phase 9 post-run consistency checks.
-- Usage:
--   docker compose exec postgres psql -U postgres -d financial_events -f /path/in/container
-- Or copy the query into psql after running a k6 scenario.

\set ON_ERROR_STOP on

SELECT
    COUNT(*) AS duplicated_ledger_event_count
FROM (
    SELECT transaction_event_id
    FROM ledger_entries
    GROUP BY transaction_event_id
    HAVING COUNT(*) > 1
) duplicated_ledger_events;

SELECT
    COUNT(*) AS duplicated_external_event_count
FROM (
    SELECT external_event_id
    FROM transaction_events
    GROUP BY external_event_id
    HAVING COUNT(*) > 1
) duplicated_events;

SELECT
    external_event_id,
    COUNT(*) AS event_rows
FROM transaction_events
WHERE external_event_id LIKE 'BANK-%STORM%'
   OR external_event_id LIKE 'BANK-REDIS-DOWN%'
GROUP BY external_event_id
HAVING COUNT(*) > 1;

SELECT
    te.external_event_id,
    COUNT(le.id) AS ledger_rows
FROM transaction_events te
LEFT JOIN ledger_entries le ON le.transaction_event_id = te.id
WHERE te.external_event_id LIKE 'BANK-%STORM%'
   OR te.external_event_id LIKE 'BANK-REDIS-DOWN%'
GROUP BY te.external_event_id
HAVING COUNT(le.id) > 1;

DO $$
DECLARE
    duplicated_ledger_event_count integer;
    duplicated_external_event_count integer;
BEGIN
    SELECT COUNT(*)
    INTO duplicated_ledger_event_count
    FROM (
        SELECT transaction_event_id
        FROM ledger_entries
        GROUP BY transaction_event_id
        HAVING COUNT(*) > 1
    ) duplicated_ledger_events;

    SELECT COUNT(*)
    INTO duplicated_external_event_count
    FROM (
        SELECT external_event_id
        FROM transaction_events
        GROUP BY external_event_id
        HAVING COUNT(*) > 1
    ) duplicated_events;

    IF duplicated_ledger_event_count > 0 THEN
        RAISE EXCEPTION 'Consistency gate failed: duplicated ledger event count=%',
            duplicated_ledger_event_count;
    END IF;

    IF duplicated_external_event_count > 0 THEN
        RAISE EXCEPTION 'Consistency gate failed: duplicated external event count=%',
            duplicated_external_event_count;
    END IF;

    RAISE NOTICE 'Consistency gate passed: duplicated ledger event count=%, duplicated external event count=%',
        duplicated_ledger_event_count,
        duplicated_external_event_count;
END $$;
