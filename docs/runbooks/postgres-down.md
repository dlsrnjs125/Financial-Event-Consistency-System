# PostgreSQL Down Runbook

## 1. 장애 상황

PostgreSQL primary에 연결할 수 없거나 write transaction을 시작할 수 없는 상태다.
PostgreSQL은 Source of Truth이므로 신규 금융 write는 성공으로 응답하지 않는다.

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

## 6. 복구 검증

- `/ready` 200 회복
- duplicate ledger count 0
- duplicate external event count 0
- orphan idempotency count 0
- stale PROCESSING은 자동 복구 또는 recovery case로 분리

## 7. 재발 방지

- DB HA/managed HA 검토
- stale connection pool recycle 기준 보강
- write suspend drill 자동화
- 외부 retry contract 문서화

## 8. README/블로그 기록 문장

PostgreSQL down 상황에서는 신규 금융 거래를 성공으로 응답하지 않고 `503`과 `Retry-After`로 재시도를 유도했다.
복구 후 동일 idempotency key와 consistency SQL로 중복 반영이 없음을 검증한다.
