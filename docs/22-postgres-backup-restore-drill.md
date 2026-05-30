# Ops Phase 4 - PostgreSQL Backup / Restore DR Drill

## 1. 문제 정의

금융 이벤트 시스템에서 PostgreSQL은 `TransactionEvent`, `LedgerEntry`,
`Account`, `IdempotencyRecord`의 최종 정합성 저장소다.
백업 파일이 존재한다는 사실만으로는 장애 복구 가능성을 증명할 수 없다.

이번 Phase의 목표는 dump 파일 생성이 아니라, 별도 restore DB에 복원한 뒤
복원된 데이터가 금융 정합성 기준을 만족하는지 검증하는 것이다.

## 2. Backup, Restore, DR Drill 구분

| 개념 | 의미 |
|---|---|
| Backup | 운영 DB에서 `pg_dump -Fc` custom format dump를 생성한다. |
| Restore | dump 파일을 운영 DB가 아닌 별도 restore DB에 복원한다. |
| DR Drill | backup, checksum, restore, schema 확인, 정합성 SQL, report 작성을 한 번에 수행한다. |

## 3. Source DB와 Restore DB 분리

Docker Compose는 source DB와 restore DB를 분리한다.

```text
postgres         : source DB, financial_events
postgres-restore : restore verification DB, financial_events_restore
```

restore 검증은 운영 DB에 절대 덮어쓰지 않는다.
`postgres-restore`는 host loopback `127.0.0.1:5433`에만 bind하며,
운영 DB volume을 공유하지 않는다.

## 4. Checksum 검증 이유

dump 파일은 장애 복구 시점의 마지막 안전망이다.
파일이 잘렸거나 전송 중 손상되면 restore가 실패하거나,
더 위험하게는 불완전한 데이터로 복구될 수 있다.

따라서 `scripts/postgres_backup.sh`는 dump와 함께 `.sha256` 파일을 생성한다.
`scripts/postgres_restore_drill.sh`는 checksum 파일이 있으면 restore 전에 반드시
검증한다. checksum 실패 시 restore는 중단된다.

`make ops4-restore`는 기존 dump 수동 복원을 위해 checksum 파일이 없으면
`SKIPPED`로 기록하고 restore를 진행할 수 있다.
반면 `make ops4-drill`과 `make ops4-demo`는 DR Drill이므로 checksum 파일을
필수로 요구한다.

checksum 파일은 실행 시 로컬에서 생성되며 git에 커밋하지 않는다.
커밋되는 report에는 checksum 검증 상태만 남긴다.

## 5. 정합성 검증 기준

복원 후 `scripts/sql/dr_consistency_check.sql`은 row data를 출력하지 않고
count만 반환한다.

| 검증 항목 | PASS 기준 |
|---|---:|
| duplicated external event | 0 |
| duplicated ledger event reference | 0 |
| orphan ledger | 0 |
| completed event without ledger | 0 |
| ledger/account mismatch | 0 |
| duplicated idempotency key | 0 |
| account balance mismatch | 0 |

`completed_event_without_ledger_count`는 `COMPLETED` 또는 `SETTLED` 상태의
거래 이벤트가 ledger 없이 남는 경우를 잡는다.

`account.balance`는 ledger가 존재하는 계좌에 대해 최신
`ledger_entries.balance_after`와 일치해야 한다.
초기 seed balance처럼 ledger 생성 전 잔액은 ledger sum으로 역산하지 않는다.

## 6. 운영 DB에 직접 Restore하지 않는 이유

restore 검증은 장애 대응 훈련이어야 하며, 운영 데이터 파괴 작업이 되면 안 된다.
운영 DB에 dump를 직접 restore하면 현재 데이터가 사라지거나 sequence, constraint,
idempotency record가 과거 상태로 되돌아갈 수 있다.

따라서 모든 restore 명령은 `postgres-restore/financial_events_restore`만 대상으로 한다.
`ops4-cleanup`도 restore DB 컨테이너만 정리하고 운영 DB volume은 삭제하지 않는다.

## 7. Dump 파일을 Git에 커밋하지 않는 이유

DB dump에는 계좌번호, 거래 이벤트, idempotency response body 같은 민감 데이터가
포함될 수 있다. checksum 파일도 dump 파일명과 운영 시간을 드러낼 수 있으므로
기본적으로 커밋하지 않는다.

`.gitignore`는 다음 파일을 제외한다.

```text
backups/postgres/*.dump
backups/postgres/*.sql
backups/postgres/*.sha256
backups/postgres/*.log
```

report에는 실제 row data를 남기지 않고 table/schema 확인 결과와 정합성 count만
기록한다.

## 8. Report 커밋 기준

`reports/dr/ops4-postgres-restore-drill.md`는 sample template이 아니라
로컬 Docker Compose 환경에서 실행한 curated evidence report다.

반복 실행 시 backup filename, duration, backup size는 바뀔 수 있다.
PR에 report를 포함할 때는 실제 증거로 남길 실행 결과인지 확인한 뒤 커밋한다.
`Backup 생성` 항목은 전체 DR Drill에서는 `PASS`, 기존 dump를 복원한
restore-only 실행에서는 `EXISTING_DUMP`로 기록된다.

## 9. 명령

```bash
make ops4-up
make ops4-backup
DUMP_FILE=backups/postgres/financial_events_YYYYMMDDTHHMMSS.dump make ops4-restore
make ops4-check
make ops4-drill
make ops4-demo
```

`make ops4-restore`는 `DUMP_FILE`이 없으면 `backups/postgres/*.dump` 중
최신 파일을 사용한다.

## 10. 이번 Phase 제외 범위

PITR/WAL archiving은 이번 Phase에서 제외한다.
로컬 Docker Compose DR Drill의 목표는 논리 백업의 복구 가능성과 정합성 검증을
재현 가능하게 만드는 것이다.

대용량 restore time 측정, object storage 업로드, encryption, retention policy,
WAL archive 기반 특정 시점 복구는 운영 환경별 스토리지와 보안 정책이 필요하므로
후속 고도화 범위로 남긴다.

## 11. 향후 확장 계획

- S3/Object Storage 업로드와 immutable backup bucket 적용
- backup retention policy와 lifecycle rule
- dump encryption과 key rotation
- PITR/WAL archiving
- restore duration/RTO 측정 자동화
- restore DB에서 reconciliation report 자동 보관
