# PostgreSQL이 죽었을 때 성공 응답도, 장애 기록 유실도 막고 싶었다

Redis down과 PostgreSQL down은 다르다. Redis는 보조 계층이지만 PostgreSQL은 최종 Source of Truth다.

PostgreSQL write path가 불가능하면 신규 금융 write를 성공으로 응답할 근거가 없다.

## DB commit 근거가 없으면 COMPLETED를 말할 수 없다

PostgreSQL이 down된 상태에서 `200 OK`나 `COMPLETED`를 반환하면 외부 시스템은 거래가 끝났다고 믿는다. 하지만 내부에는 commit evidence가 없다.

그래서 PostgreSQL write path 장애 시에는 신규 금융 write를 성공으로 처리하지 않고, `503 + Retry-After`로 명확히 재시도 가능한 실패를 반환했다.

```text
DB write unavailable
-> new financial write blocked
-> 503 Service Unavailable
-> Retry-After returned
```

## 왜 임시 큐에 저장하지 않았나

DB down 중 파일, Redis, memory queue에 요청을 쌓아두는 선택지도 있다. 하지만 그렇게 하면 API 응답 의미가 달라진다.

요청을 durable queue에 넣고 나중에 처리한다면 응답은 `COMPLETED`가 아니라 `ACCEPTED`에 가깝다. 외부 시스템과의 API 계약도 "최종 원장 반영 완료"가 아니라 "처리 예약"으로 바뀌어야 한다.

현재 시스템은 PostgreSQL commit을 기준으로 거래 완료를 말한다. 그래서 DB down 중 임시 저장을 만들기보다, 명확하게 실패시키고 같은 Idempotency-Key로 재시도하게 했다.

## DB down drill에서 확인한 순서

DB down drill에서는 다음 순서를 확인했다.

1. 정상 상태 baseline write 성공
2. PostgreSQL stop
3. `/ready` 실패
4. 신규 write `503 + Retry-After`
5. write suspend artifact 생성
6. PostgreSQL start
7. blocked event가 성공 기록으로 남지 않았는지 확인
8. operator resume
9. 동일 `external_event_id` / `Idempotency-Key` 재시도
10. event count 1, ledger count 1
11. duplicate event / ledger count 0

재현 명령은 local Docker Compose 기준이다.

```bash
make ph1-db-down-drill
make ph2-db-down-incident-artifact
```

## 그런데 DB가 죽었는데 장애 증거는 어디에 남길까

DB down 중에는 incident record도 DB에 쓰기 어렵다. 그래서 DB 밖에 out-of-band incident artifact를 남기도록 했다.

```text
reports/incidents/{incident_id}/
  manifest.json
  sanitized-report.md
  write-suspend-state.json
  consistency-summary.json
```

이 artifact는 복구 실행 기록이 아니라 장애 중 수집 가능한 sanitized evidence다.

## 손상된 state file도 evidence로 남긴 이유

DB down drill 중 `write-suspend-state.json`이 깨질 수 있다. 이때 artifact 생성까지 실패하면 장애 증거 수집이라는 목적이 무너진다.

그래서 JSON parse 실패를 fatal error로 보지 않고 `invalid_state_json` summary로 남겼다.

```json
{
  "active": true,
  "reason": "state_file_invalid",
  "source": "artifact_parse_failed",
  "result": "invalid_state_json",
  "sensitive_data_included": false
}
```

장애 기록기는 정상 상황에서만 동작하면 안 된다고 판단했다.

## 트러블슈팅 1: resume했는데도 계속 WRITE_SUSPENDED가 반환됐다

PostgreSQL을 다시 올리고 operator resume을 실행했는데도 retry write가 계속 503을 반환한 적이 있었다.

원인은 host CLI가 보는 `reports/runtime`과 API container 내부 `/app/reports/runtime`이 서로 다른 경로였기 때문이다. 운영자가 resume했다고 생각한 state file을 API process는 보지 못하고 있었다.

그래서 Docker Compose에 bind mount를 추가해 CLI와 API가 같은 runtime artifact를 보도록 고정했다.

```yaml
./reports/runtime:/app/reports/runtime
```

write suspend는 state file 하나로도 운영 의미가 달라진다. operator command와 API process가 같은 evidence를 보고 있는지까지 검증해야 했다.

## 트러블슈팅 2: DB probe가 실제 거래 transaction과 충돌했다

DB가 살아 있는지 확인하려고 같은 session에서 `SELECT 1` probe를 먼저 실행했다.

그런데 SQLAlchemy autobegin 때문에 이미 transaction이 열린 상태가 되었고, 이후 service transaction을 시작할 때 다음 예외가 발생했다.

```text
A transaction is already begun on this Session
```

해결은 probe 성공/실패 후 `rollback()`으로 probe transaction을 명시적으로 닫는 것이었다.

availability check도 transaction boundary 안에서는 부작용이 될 수 있다는 점을 확인했다.

## 남은 한계

이 단계는 durable queue를 구현하지 않는다. queue-first architecture를 도입하려면 `ACCEPTED`와 `COMPLETED`를 분리하고, consumer idempotency, replay, DLQ, operator visibility까지 다시 설계해야 한다.

현재 설계의 목표는 DB write 불가능 상황에서 성공을 거짓으로 말하지 않고, 동시에 장애 evidence를 DB 밖에 안전하게 남기는 것이다.
