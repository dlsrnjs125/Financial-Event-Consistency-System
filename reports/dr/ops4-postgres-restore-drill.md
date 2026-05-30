# Ops Phase 4 - PostgreSQL Backup / Restore DR Drill

## 목적

백업 파일 생성이 아니라 복구 가능성과 복구 후 정합성을 검증한다.

## 실행 명령

```bash
make ops4-demo
```

## 실행 증거 기준

이 report는 `make ops4-demo` 또는 `make ops4-drill`을 로컬 Docker Compose 환경에서
실행한 curated evidence report이다.
실제 dump 파일과 checksum 파일은 민감 정보 포함 가능성이 있어 git에 커밋하지 않는다.
checksum 파일은 실행 시 로컬에서 생성되며, 이 report에는 checksum 검증 상태와
count-only 정합성 결과만 남긴다.
`Backup 생성` 항목은 전체 DR Drill에서는 `PASS`, 기존 dump를 복원한
restore-only 실행에서는 `EXISTING_DUMP`로 기록된다.

## 결과 요약

| 항목 | 결과 |
|---|---:|
| Backup 생성 | PASS |
| SHA256 checksum 생성 | PASS |
| Checksum 검증 | PASS |
| Restore DB 복원 | PASS |
| Schema 확인 | PASS |
| Duplicated external event | 0 |
| Duplicated ledger event | 0 |
| Orphan ledger | 0 |
| Completed event without ledger | 0 |
| Ledger account mismatch | 0 |
| Duplicated idempotency key | 0 |
| Account balance consistency | PASS |
| Restore duration seconds | 1 |
| DR drill duration seconds | 2 |
| DR Drill | PASS |

## 복구 대상

- Source DB: postgres / financial_events
- Restore DB: postgres-restore / financial_events_restore
- Backup file: `financial_events_20260530T194900.dump`
- Backup size: `24K`
- DR drill started at: `2026-05-30T10:49:00Z`
- Restore started at: `2026-05-30T10:49:01Z`

## 운영 원칙

- 운영 DB에 직접 restore하지 않는다.
- restore 검증은 별도 DB에서 수행한다.
- dump 파일과 checksum은 git에 커밋하지 않는다.
- report에는 실제 row data를 기록하지 않는다.

## 검증 SQL 결과

```text
account_balance_mismatch_count=0
completed_event_without_ledger_count=0
duplicated_external_event_count=0
duplicated_idempotency_key_count=0
duplicated_ledger_event_count=0
ledger_account_mismatch_count=0
orphan_ledger_count=0
```

## 한계

- PITR/WAL archiving은 이번 Phase 범위에서 제외한다.
- 대용량 restore time 측정은 후속 단계에서 수행한다.
- 클라우드 object storage 업로드는 구현하지 않는다.
