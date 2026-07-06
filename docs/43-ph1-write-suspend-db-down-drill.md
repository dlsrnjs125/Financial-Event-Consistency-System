# PH1 Write Suspend and PostgreSQL Down Drill

## 1. Goal

PH1의 목표는 PostgreSQL write path가 불가능할 때 신규 금융 거래를 성공으로 응답하지 않는 것이다.
PostgreSQL은 최종 Source of Truth이므로 DB down 중 `transaction_events`, `ledger_entries`, `accounts.balance`, `idempotency_records`를 일관되게 기록할 수 없다.

따라서 PH1은 다음을 구현한다.

- runtime write suspend state
- local out-of-band state artifact
- 금융 write endpoint `503 Service Unavailable` + `Retry-After`
- PostgreSQL probe 실패 또는 DB 예외 시 자동 suspend
- 운영자 수동 resume
- Docker Compose 기반 PostgreSQL down drill

## 2. Scope

포함:

- `POST /api/v1/transaction-events` write guard
- `reports/runtime/write-suspend-state.json` 상태 파일
- `scripts/write_suspend_state.py` CLI
- `scripts/ph1_db_down_drill.sh` drill
- `make ph1-db-down-drill`
- `make ph1-write-suspend-status`
- `make ph1-write-suspend-resume`
- `financial_write_suspended_total{reason,route_group}`
- `financial_write_suspend_state{reason}`

제외:

- `recovery_cases` DB table
- `incident_events` DB table
- full incident analyzer
- AI sanitizer
- multi-node global control plane
- PostgreSQL HA cluster
- durable queue architecture
- latency attribution instrumentation

## 3. Architecture

```text
POST /api/v1/transaction-events
  -> HMAC dependency
  -> write suspend guard
       -> active artifact/runtime state: 503 + Retry-After
       -> DB SELECT 1 probe failure: enable suspend, artifact write, 503
  -> idempotency
  -> transaction service
  -> PostgreSQL transaction
```

`/health`, `/ready`, `/metrics`는 write suspend guard 대상이 아니다.
`/ready`는 PostgreSQL down을 계속 드러내야 하므로 write suspend로 숨기지 않는다.

## 4. State Storage

기본 설정:

```text
WRITE_SUSPEND_STATE_FILE=reports/runtime/write-suspend-state.json
WRITE_SUSPEND_RETRY_AFTER_SECONDS=30
```

state JSON 필드:

```json
{
  "active": true,
  "reason": "postgres_unavailable",
  "activated_at": "2026-07-06T00:00:00Z",
  "activated_by": "api",
  "retry_after_seconds": 30,
  "source": "postgres_probe",
  "run_id": "write-suspend-abc123"
}
```

resume 후에는 `resumed_at`, `resumed_by`, `resume_reason`이 추가된다.
artifact에는 raw account number, raw idempotency key, raw request body, HMAC signature, secret을 저장하지 않는다.
Docker Compose에서는 `./reports/runtime`을 `/app/reports/runtime`으로 mount해 host CLI와 API process가 같은 artifact를 본다.

## 5. Unavailable Flow

1. 금융 write 요청이 들어온다.
2. write suspend state가 active이면 즉시 `503`을 반환한다.
3. inactive이면 같은 요청 세션으로 `SELECT 1` probe를 실행한다.
4. probe 또는 SQLAlchemy DB 예외가 실패하면 `postgres_unavailable`로 suspend를 활성화한다.
5. API는 `Retry-After` header와 `WRITE_SUSPENDED` body를 반환한다.
6. DB가 회복되어도 자동 resume하지 않는다.
7. 운영자가 consistency evidence를 확인하고 resume한다.

응답 예시:

```text
HTTP/1.1 503 Service Unavailable
Retry-After: 30
```

```json
{
  "error_code": "WRITE_SUSPENDED",
  "message": "Financial write traffic is temporarily suspended.",
  "retryable": true,
  "request_id": "req-...",
  "trace_id": "trace-..."
}
```

## 6. Operator Commands

```bash
scripts/write_suspend_state.py status
scripts/write_suspend_state.py enable --reason postgres_unavailable
scripts/write_suspend_state.py disable --reason operator_resume
```

Makefile:

```bash
make ph1-write-suspend-status
make ph1-write-suspend-resume
make ph1-db-down-drill
make ops9-db-down-drill
```

`ops9-db-down-drill`은 PH1 drill alias다.

## 7. Drill Method

`scripts/ph1_db_down_drill.sh`는 다음 순서로 실행된다.

1. Docker Compose stack을 시작한다.
2. `/health`, `/ready` baseline을 확인한다.
3. baseline transaction write가 성공하는지 확인한다.
4. PostgreSQL container를 stop한다.
5. `/ready`가 실패하는지 확인한다.
6. 금융 write가 `503` + `Retry-After`를 반환하는지 확인한다.
7. write suspend state artifact 존재를 확인한다.
8. PostgreSQL container를 start한다.
9. `/ready` 회복을 확인한다.
10. blocked external event가 성공 기록으로 남지 않았는지 확인한다.
11. duplicate event/ledger count가 0인지 확인한다.
12. operator resume을 실행한다.
13. 새 write가 정상 처리되는지 확인한다.
14. evidence report를 생성한다.

evidence 경로:

```text
reports/production-hardening/ph1-write-suspend/{run_id}/report.md
```

## 8. Verification

자동 테스트:

- write suspend artifact missing이면 inactive
- enable 상태가 artifact에 저장되고 재로딩된다
- disable 시 resume metadata가 저장된다
- active state에서 `POST /transaction-events`는 `503` + `Retry-After`
- active state에서 `/health`는 차단되지 않는다
- DB probe 실패 시 `postgres_unavailable`로 suspend된다

권장 로컬 검증:

```bash
make test-unit
make test-integration
make scripts-check
make security-log-check
make ph1-db-down-drill
```

## 9. Troubleshooting

- 기존 `reports/runtime/write-suspend-state.json`이 active이면 write 테스트가 계속 503을 반환할 수 있다. `make ph1-write-suspend-resume`으로 명시적으로 해제한다.
- Docker daemon이 실행 중이어야 `make ph1-db-down-drill`을 실행할 수 있다.
- drill 중 실패해도 cleanup trap이 PostgreSQL container를 다시 start하려고 시도한다.
- baseline write가 실패하면 먼저 계정 seed와 HMAC client 설정을 확인한다.

## 10. Limitations

- PH1은 단일 API 인스턴스와 local artifact 기준이다.
- multi-node production에서는 Nginx/LB write route blocking 또는 shared control plane이 필요하다.
- DB 복구 후 `incident_events`/`recovery_cases` backfill은 후속 PH2/PH3 범위다.
- PostgreSQL HA와 durable queue 도입은 `docs/40-postgres-ha-and-queue-tradeoff-adr.md`에서 별도 판단한다.

## 11. Follow-up

- out-of-band incident artifact bundle 고도화
- incident analyzer MVP
- recovery case DB model과 manual approval workflow
- stale PROCESSING recovery
- multi-node write suspend drift detection
