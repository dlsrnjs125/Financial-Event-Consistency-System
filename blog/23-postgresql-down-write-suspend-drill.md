# 23편. PostgreSQL이 죽었을 때 성공 응답을 주지 않는 법: Write Suspend Drill

## 1. 왜 Redis down과 PostgreSQL down은 다른가

Redis는 이 프로젝트에서 lock/cache 보조 계층이다.
Redis가 내려가면 성능과 중복 요청 완화에는 영향이 있지만, PostgreSQL transaction과 unique constraint가 살아 있다면 최종 정합성은 유지할 수 있다.

PostgreSQL은 다르다.
`transaction_events`, `ledger_entries`, `accounts.balance`, `idempotency_records`를 기록할 수 없다면 서버는 거래가 확정됐다고 말할 근거가 없다.
그래서 PostgreSQL write path가 불가능한 순간 신규 금융 write는 성공 응답이 아니라 `503 Service Unavailable`과 `Retry-After`를 반환해야 한다.

## 2. PH1에서 구현한 것

PH1에서는 runtime write suspend를 추가했다.

- `POST /api/v1/transaction-events`에만 write guard를 적용한다.
- active 상태에서는 `503` + `Retry-After`를 반환한다.
- PostgreSQL probe 실패 또는 DB 예외가 발생하면 `postgres_unavailable`로 suspend를 활성화한다.
- 상태는 runtime memory와 `reports/runtime/write-suspend-state.json`에 남긴다.
- `/health`, `/ready`, `/metrics`는 차단하지 않는다.
- resume은 자동이 아니라 운영자가 명시적으로 수행한다.

핵심은 장애를 성공으로 위장하지 않는 것이다.
DB가 회복됐다는 사실만으로 write를 자동 재개하지 않고, consistency evidence를 확인한 뒤 운영자가 resume한다.

## 3. Drill 흐름

`make ph1-db-down-drill`은 Docker Compose 환경에서 다음을 확인한다.

1. 정상 상태의 baseline write 성공
2. PostgreSQL stop
3. `/ready` 실패
4. 신규 write `503` + `Retry-After`
5. write suspend artifact 생성
6. PostgreSQL start
7. blocked event가 성공 기록으로 남지 않았는지 확인
8. duplicate event/ledger count 0
9. operator resume
10. 새 write 정상 처리

evidence는 `reports/production-hardening/ph1-write-suspend/{run_id}/report.md`에 남긴다.

## 4. 왜 임시 큐에 저장하지 않았나

DB down 중 요청을 파일이나 Redis에 쌓아 두고 나중에 반영하는 방법도 있다.
하지만 이 프로젝트의 API 계약은 PostgreSQL transaction 결과를 기준으로 처리 완료를 말한다.
durable queue를 도입하려면 응답 의미가 `COMPLETED`가 아니라 `ACCEPTED`로 바뀌어야 한다.

이번 PH1에서는 API 계약을 바꾸지 않는다.
그래서 DB가 Source of Truth인 현재 구조에서는 fail-closed를 선택했다.

## 5. 남은 과제

PH1은 단일 API 인스턴스와 local artifact 기준이다.
실제 다중 인스턴스 운영에서는 Nginx/LB route blocking, shared control plane, instance drift detection이 필요하다.

또한 DB 복구 후 incident artifact를 `incident_events`와 `recovery_cases`로 backfill하는 흐름은 후속 Phase에서 구현한다.
