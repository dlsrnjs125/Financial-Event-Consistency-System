# Ops Phase 3 - Backup, Restore, DR Drill

## 1. 해결하려는 운영 문제

백업 파일이 존재한다는 사실과 실제로 복구 가능하다는 사실은 다르다.

금융 이벤트 시스템에서는 장애 이후 PostgreSQL을 복원했을 때 거래 원장과 계좌 잔액이 일치해야 한다.

Ops Phase 3의 목표는 `pg_dump` 파일을 만드는 것이 아니라, 별도 restore DB에 복원하고 정합성 SQL까지 실행하는 DR Drill을 구성하는 것이다.

## 2. 구현 범위

- `pg_dump` 기반 논리 백업
- 백업 파일 압축
- checksum 생성
- restore 전용 DB 복원
- 정합성 검증 SQL 실행
- 오래된 백업 정리 정책
- DR Drill 결과 Markdown/JSON report 생성

## 3. 제외 범위

- PITR/WAL archive 구성은 제외한다.
- cloud snapshot backup은 제외한다.
- 운영 DB 자동 삭제나 destructive restore는 제외한다.
- DB schema downgrade rollback은 제외한다.

## 4. 파일/디렉터리 변경 계획

```text
scripts/
  backup/
    pg_backup.sh
    pg_restore.sh
    verify_backup.sh
    cleanup_old_backups.sh
    verify_restore.sql

backups/
  20260529_020000/
    financial_events_20260529_020000.dump.gz
    financial_events_20260529_020000.sha256
    metadata.json
    verify_result.json

reports/
  dr-drill/
    20260529_020000_dr_result.md
    20260529_020000_verify_result.json
```

## 5. 검증 명령어

```bash
make backup-db
make verify-backup
make restore-db
make verify-restore
make dr-drill
```

성공 기준:

- 백업 파일 생성 성공
- checksum 검증 성공
- restore 전용 DB 복원 성공
- 정합성 검증 SQL 결과 모두 0건
- restore duration 10분 이내
- DR Drill 결과 Markdown 자동 생성

## 6. 완료 기준과 README에 남길 결과

### metadata.json

```json
{
  "backup_started_at": "2026-05-29T02:00:00+09:00",
  "backup_finished_at": "2026-05-29T02:00:09+09:00",
  "database": "financial_events",
  "backup_type": "pg_dump_custom",
  "compressed": true,
  "checksum_algorithm": "sha256",
  "schema_version": "alembic_revision_xxx"
}
```

### 스크립트별 책임

| 스크립트 | 책임 | 실패 조건 |
|---|---|---|
| `pg_backup.sh` | dump 생성, gzip, metadata 생성 | dump exit code != 0 |
| `verify_backup.sh` | checksum 검증 | sha256 불일치 |
| `pg_restore.sh` | restore DB 초기화 후 복원 | restore 실패 |
| `verify_restore.sql` | 정합성 SQL 실행 | 결과 1건 이상 |
| `cleanup_old_backups.sh` | 보관 기간 초과 파일 삭제 | dry-run 없이 삭제 금지 |

### 정합성 검증 SQL

```sql
SELECT external_event_id, COUNT(*)
FROM ledger_entries
GROUP BY external_event_id
HAVING COUNT(*) > 1;

SELECT id, external_event_id, status, updated_at
FROM transaction_events
WHERE status IN ('RECEIVED', 'VALIDATED', 'PROCESSING')
  AND updated_at < NOW() - INTERVAL '10 minutes';

SELECT i.idempotency_key
FROM idempotency_records i
LEFT JOIN transaction_events e ON i.transaction_event_id = e.id
WHERE e.id IS NULL;

SELECT a.id, a.account_no, a.balance, COALESCE(SUM(l.amount), 0) AS ledger_sum
FROM accounts a
LEFT JOIN ledger_entries l ON a.id = l.account_id
GROUP BY a.id, a.account_no, a.balance
HAVING a.balance <> COALESCE(SUM(l.amount), 0);
```

README에는 다음 결과를 남긴다.

- backup duration
- restore duration
- backup file size
- checksum result
- restored table count
- duplicated ledger count
- balance mismatch count
- orphan idempotency count
- RTO actual
- RPO assumption
