# Backup, Restore, DR Drill

## 1. 목적

장애 대응은 서비스 재시작만으로 끝나지 않는다. 금융 이벤트 시스템에서는 PostgreSQL 백업 파일이 실제로 복구 가능한지, 복원 후 ledger/account 정합성이 유지되는지 검증해야 한다.

## 2. 스크립트 구조

```text
scripts/backup/
  pg_backup.sh
  pg_restore.sh
  verify_backup.sh
  cleanup_old_backups.sh
```

## 3. 백업/복구 흐름

1. `pg_dump` 기반 논리 백업 생성
2. 백업 파일 압축
3. checksum 생성
4. restore 전용 DB에 복원
5. ledger/account 정합성 SQL 실행
6. 오래된 백업 삭제 정책 적용

## 4. 검증 SQL

```sql
SELECT external_event_id, COUNT(*)
FROM ledger_entries
GROUP BY external_event_id
HAVING COUNT(*) > 1;

SELECT a.account_no, a.balance, COALESCE(SUM(l.amount), 0) AS ledger_sum
FROM accounts a
LEFT JOIN ledger_entries l ON a.id = l.account_id
GROUP BY a.account_no, a.balance;
```

## 5. 운영 기준

| 항목 | 목표 |
|---|---|
| RPO | 로컬 기준 최근 백업 시점까지 |
| RTO | 10분 이내 복원 |
| 백업 검증 | checksum + restore 검증 |
| 정합성 검증 | ledger/account 불일치 0건 |

## 6. Makefile 목표

```bash
make backup-db
make restore-db
make verify-restore
make dr-drill
```

## 7. README 요약 문장

장애 대응은 서비스 재시작만으로 끝나지 않는다고 판단했다. PostgreSQL 백업 파일이 실제로 복구 가능한지 검증하기 위해 별도 restore DB에 복원하고, ledger/account 정합성 SQL을 자동 실행하는 DR Drill을 구성한다.
