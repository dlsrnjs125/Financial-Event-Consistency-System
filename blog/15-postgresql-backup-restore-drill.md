# 15편. PostgreSQL 백업은 만들어지는 것보다 복구되는 것이 중요하다

## 1. 백업 파일은 안심의 증거가 아니다

백업은 만들어지는 것이 아니라 복구되어야 의미가 있다.
금융 이벤트 시스템에서는 dump 파일 존재보다 복원 후 ledger, event, account,
idempotency 정합성이 유지되는지가 더 중요하다.

이 프로젝트에서 PostgreSQL은 최종 Source of Truth다.
`TransactionEvent`가 한 번만 저장되고, `LedgerEntry`가 한 번만 반영되며,
`Account.balance`가 ledger 결과와 맞고, `IdempotencyRecord`가 재시도 응답의
기준으로 남아야 한다.

그래서 Ops Phase 4의 목표는 `pg_dump` 성공 메시지가 아니다.
별도 restore DB에 복원하고, 정합성 SQL 결과가 모두 0인지 확인하는 것이다.

## 2. Backup, Restore, DR Drill을 분리했다

이번 단계에서는 세 단어를 엄격히 구분했다.

| 개념 | 질문 |
|---|---|
| Backup | 운영 DB에서 dump 파일을 만들 수 있는가? |
| Restore | 그 dump 파일이 별도 DB에 실제로 복원되는가? |
| DR Drill | 복원된 DB가 금융 정합성 기준을 통과하는가? |

구현 흐름은 다음과 같다.

```text
postgres/financial_events
  -> pg_dump -Fc
  -> SHA256 checksum
  -> postgres-restore/financial_events_restore
  -> pg_restore
  -> schema/table check
  -> scripts/sql/dr_consistency_check.sql
  -> reports/dr/ops4-postgres-restore-drill.md
```

## 3. 운영 DB에 복원하지 않는다

가장 중요한 원칙은 단순하다.

```text
절대 운영 DB에 restore하지 않는다.
```

Docker Compose에 `postgres-restore` 서비스를 추가하고, restore 대상 DB 이름도
`financial_events_restore`로 분리했다.
host port는 `127.0.0.1:5433`에만 bind해서 로컬 검증용 DB라는 경계를 명확히 했다.

```text
postgres         : source DB, financial_events
postgres-restore : restore DB, financial_events_restore
```

`ops4-cleanup`도 restore DB 컨테이너만 정리한다.
운영 DB volume은 삭제하지 않는다.

## 4. 실제 스크립트 구조

구현은 repo의 기존 운영 스크립트 패턴에 맞춰 세 파일로 나눴다.

```text
scripts/postgres_backup.sh
scripts/postgres_restore_drill.sh
scripts/postgres_dr_drill.sh
scripts/sql/dr_consistency_check.sql
```

`scripts/postgres_backup.sh`는 운영 DB 컨테이너에서 `pg_dump -Fc`를 실행하고,
dump 파일과 `.sha256` checksum을 생성한다.

`scripts/postgres_restore_drill.sh`는 checksum을 검증한 뒤
`postgres-restore/financial_events_restore`에만 restore한다.
기존 dump를 수동 복원하는 `make ops4-restore`에서는 checksum 파일이 없으면
`SKIPPED`로 기록할 수 있지만, `make ops4-drill`과 `make ops4-demo`는 checksum을
필수로 요구한다.

`scripts/postgres_dr_drill.sh`는 backup부터 restore, consistency check,
report 작성까지 한 번에 실행하는 wrapper다.

## 5. 복원 후 정합성 SQL을 실행한다

복원 성공은 테이블이 생겼다는 뜻일 뿐이다.
금융 이벤트 시스템에서는 다음 위반 count가 모두 0이어야 한다.

| 검증 항목 | PASS 기준 |
|---|---:|
| duplicated external event | 0 |
| duplicated ledger event reference | 0 |
| orphan ledger | 0 |
| completed event without ledger | 0 |
| ledger/account mismatch | 0 |
| duplicated idempotency key | 0 |
| account balance mismatch | 0 |
| sequence position lag | 0 |

특히 `completed_event_without_ledger_count`는 거래가 성공 상태인데 원장 반영이
없는 경우를 잡는다. 반대로 `orphan_ledger_count`는 원장이 이벤트 없이 남은
경우를 잡는다.

`sequence_position_lag_count`는 restore 후 sequence가 `MAX(id)`보다 낮아
복구 직후 첫 insert가 PK 충돌로 실패할 수 있는 상태를 잡는다.

검증 SQL은 실제 row data를 출력하지 않는다.
report에는 count와 PASS/FAIL만 남긴다.
dump에는 계좌/거래 데이터가 들어갈 수 있기 때문에 `backups/postgres/*.dump`와
`*.sha256`은 git에 커밋하지 않는다.

DR Drill은 count가 0인지뿐 아니라, 필수 검증 항목이 모두 실행되었는지도 확인한다.
또 restore duration과 전체 drill duration을 report에 남겨 RTO 기준도 확인한다.

## 6. 재현 명령

전체 흐름은 한 명령으로 재현한다.

```bash
make ops4-demo
```

개별 단계는 다음처럼 실행할 수 있다.

```bash
make ops4-up
make ops4-backup
DUMP_FILE=backups/postgres/financial_events_YYYYMMDDTHHMMSS.dump make ops4-restore
make ops4-check
make ops4-drill
```

결과 report는 `reports/dr/ops4-postgres-restore-drill.md`에 기록된다.
이 report는 template이 아니라 로컬 Docker Compose 환경에서 실행한
curated evidence report다.

## 7. 이번 단계에서 일부러 하지 않은 것

이번 Phase는 로컬 Docker Compose 기반 논리 백업 복구 훈련이다.
그래서 다음은 후속 고도화 범위로 남겼다.

- PITR/WAL archiving
- S3/Object Storage 업로드
- backup retention policy
- dump encryption
- 대용량 restore time/RTO 측정 고도화
- 초기 잔액 + ledger 누적합 기반의 전체 reconciliation
- ledger chain 연속성 검증

먼저 필요한 것은 복잡한 백업 플랫폼이 아니라,
"백업이 실제로 복구되고 정합성까지 유지되는가"를 반복해서 확인할 수 있는
가장 작은 훈련이다.
