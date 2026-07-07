# PostgreSQL Down Runbook

## 1. 장애 상황

PostgreSQL primary에 연결할 수 없거나 write transaction을 시작할 수 없는 상태다.
PostgreSQL은 Source of Truth이므로 신규 금융 write는 성공으로 응답하지 않는다.

Severity: SEV1

자동 조치:

- write suspend 후보 활성화
- `503` + `Retry-After` 응답
- out-of-band incident artifact 생성
- consistency check 예약

수동 승인 필요 여부: 필요

- DB 복구 또는 failover 승인
- write resume 승인

승인자: 운영 책임자 또는 incident commander

Evidence 경로:

```text
reports/incidents/{incident_id}/
reports/runtime/write-suspend-state.json
reports/production-hardening/ph1-write-suspend/{run_id}/
```

## 2. 예상 원인

- PostgreSQL process/container down
- network partition
- failover 진행 중
- disk full 또는 WAL 폭증
- stale connection pool

## 3. 사용자 영향

- 신규 거래 이벤트 `503 Service Unavailable`
- `Retry-After` 기반 재시도 필요
- `/ready` 실패 또는 degraded 표시

## 4. 탐지 방법

- `/ready` postgres fail
- app log의 connection refused/timeout
- 5xx 증가
- PostgreSQL dashboard target down

## 5. 대응 방법

1. 신규 write가 성공 응답을 반환하지 않는지 확인한다.
2. write suspend 상태를 확인한다.
3. PostgreSQL service 상태와 disk/WAL 상태를 확인한다.
4. failover 또는 복구 작업이 필요한지 판단한다.
5. 복구 후 recovery mode에서 consistency SQL을 실행한다.

PH1 운영 명령:

```bash
make ph1-write-suspend-status
make ph1-write-suspend-resume
make ph1-db-down-drill
```

PH2 incident artifact 명령:

```bash
make ph2-incident-artifact
make ph2-incident-artifact-validate
make ph2-db-down-incident-artifact
```

PH3 incident analyzer 명령:

```bash
make ph3-incident-analyze
make ph3-incident-analyze-validate
make ph3-db-down-incident-analysis
```

`POST /api/v1/transaction-events`는 write suspend active 상태에서 `503 Service Unavailable`과 `Retry-After`를 반환한다.
`/health`, `/ready`, `/metrics`는 write suspend 자체로 차단하지 않는다.
PH2 artifact는 `reports/incidents/{incident_id}/`에 저장되며 `sanitized-report.md`는 raw account number, raw idempotency key, HMAC signature, Authorization header, raw request body를 포함하지 않아야 한다.
PH3 analyzer는 sanitized artifact를 `POSTGRES_DOWN_WRITE_SUSPENDED` 같은 rule-based classification 후보로 분류하지만, DB 복구나 write resume을 자동 승인하지 않는다.

PH4 recovery case 명령:

```bash
make ph4-recovery-case-from-latest
make ph4-recovery-cases
make ph4-quarantines
```

PH4는 PH3 analyzer result를 recovery case로 등록하고 수동 승인 전 실행을 차단한다.
금전 보정, write resume 승인, compensation ledger 생성은 여전히 운영자 판단과 후속 범위다.

PH5 recovery follow-up 명령:

```bash
make ph5-reconciliation-run
make ph5-reconciliation-validate
```

PH5는 DB 복구 후 실행하는 절차이며, DB가 unavailable이면 PH1 write suspend와 PH2/PH3 incident artifact/analyzer 흐름을 먼저 사용한다.

## 6. 복구 검증

- `/ready` 200 회복
- duplicate ledger count 0
- duplicate external event count 0
- orphan idempotency count 0
- stale PROCESSING은 자동 복구 또는 recovery case로 분리

## 7. Write resume 가능 조건

- PostgreSQL primary write 가능
- stale connection pool 정리
- out-of-band artifact를 `incident_events`와 `recovery_cases`에 backfill
- unresolved SEV1 recovery case 없음 또는 quarantine 완료
- 승인자와 승인 시각 기록

## 8. Rollback/abort 조건

- consistency SQL에서 정합성 위반 발견
- recovery case 분석 전 write resume 요청
- failover primary identity 불명확
- raw sensitive data가 incident artifact에 포함됨

## 9. 재발 방지

- DB HA/managed HA 검토
- stale connection pool recycle 기준 보강
- write suspend drill 자동화
- 외부 retry contract 문서화

## 10. Postmortem 연결

- incident timeline
- out-of-band artifact path
- write suspend/resume 승인 기록
- recovery case 목록

## 11. README/블로그 기록 문장

PostgreSQL down 상황에서는 신규 금융 거래를 성공으로 응답하지 않고 `503`과 `Retry-After`로 재시도를 유도했다.
복구 후 동일 idempotency key와 consistency SQL로 중복 반영이 없음을 검증한다.
