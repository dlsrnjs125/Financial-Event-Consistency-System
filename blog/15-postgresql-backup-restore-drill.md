# 15편. PostgreSQL 백업은 만들어지는 것보다 복구되는 것이 중요하다

## 1. 문제를 어떻게 정의했는가

백업 파일이 존재한다는 사실과 실제로 복구 가능하다는 사실은 다르다.
금융 이벤트 시스템에서는 장애 이후 PostgreSQL을 복원했을 때 거래 원장과 계좌 잔액이 일치해야 한다.

그래서 백업 Phase의 목표는 `pg_dump` 파일을 만드는 것이 아니라, 별도 restore DB에 복원하고 정합성 SQL까지 실행하는 것이다.

## 2. 처음 세운 가설

처음에는 `pg_dump`만 있으면 충분해 보인다.

```bash
pg_dump financial_events > backup.sql
```

하지만 이 방식만으로는 다음 질문에 답할 수 없다.

- 백업 파일이 손상되지 않았는가?
- restore DB에 실제로 복원되는가?
- `ledger_entries` 중복 반영은 없는가?
- `accounts.balance`와 ledger 합계가 일치하는가?
- 복구에 얼마나 걸리는가?

## 3. 설계한 흐름

```text
pg_dump
  -> gzip 압축
  -> checksum 생성
  -> restore 전용 DB 생성
  -> 복원
  -> ledger/account 정합성 SQL
  -> 오래된 백업 정리
```

이 흐름을 스크립트로 나누면 다음과 같다.

```text
scripts/backup/
  pg_backup.sh
  pg_restore.sh
  verify_backup.sh
  cleanup_old_backups.sh
```

## 4. 정합성 검증 SQL

복원 후에는 단순히 테이블 수를 보는 것이 아니라 금융 정합성 기준을 확인해야 한다.

```sql
SELECT external_event_id, COUNT(*)
FROM ledger_entries
GROUP BY external_event_id
HAVING COUNT(*) > 1;
```

그리고 계좌 잔액과 원장 합계도 비교한다.

```sql
SELECT a.account_no, a.balance, COALESCE(SUM(l.amount), 0) AS ledger_sum
FROM accounts a
LEFT JOIN ledger_entries l ON a.id = l.account_id
GROUP BY a.account_no, a.balance;
```

## 5. RPO/RTO 기준

로컬 훈련 기준은 다음처럼 잡는다.

| 항목 | 목표 |
|---|---|
| RPO | 최근 백업 시점까지 |
| RTO | 10분 이내 복원 |
| 백업 검증 | checksum + restore |
| 정합성 검증 | ledger/account 불일치 0건 |

## 6. 완료 기준

```bash
make backup-db
make restore-db
make verify-restore
make dr-drill
```

백업이 생성되고, checksum이 맞고, restore DB에 복원되며, 정합성 SQL 결과가 0건이어야 한다.

## 7. 남은 한계

로컬 논리 백업은 운영 환경의 PITR, WAL archive, managed backup 정책을 대체하지 못한다.
하지만 "백업 파일이 실제로 복구 가능한가"를 검증하는 훈련은 운영 안정성의 기본선이다.

## 8. 실제 구현 후 보강할 내용

이 글은 Ops Phase 3 구현 전 설계 초안이다. 구현 후에는 다음 내용을 추가한다.

- backup duration
- restore duration
- backup file size
- checksum result
- duplicated ledger count
- balance mismatch count
- orphan idempotency count
- DR Drill 결과 Markdown
