# PostgreSQL이 죽었을 때 성공 응답도, 장애 기록 유실도 막고 싶었다

Redis down과 PostgreSQL down은 다르다. Redis는 보조 계층이지만 PostgreSQL은 최종 Source of Truth다.

PostgreSQL write path가 불가능하면 신규 금융 write를 성공으로 응답할 근거가 없다.

## DB commit 근거가 없으면 COMPLETED를 말할 수 없다

PostgreSQL이 down된 상태에서 `200 OK`나 `COMPLETED`를 반환하면 외부 시스템은 거래가 끝났다고 믿는다. 하지만 내부에는 commit evidence가 없다.

그래서 PH1에서는 PostgreSQL write path 장애 시 `503 + Retry-After`로 fail-closed 처리했다.

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

## Drill에서 확인한 순서

PH1/PH2 drill은 다음 순서를 확인한다.

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

DB down 중에는 incident record도 DB에 쓰기 어렵다. 그래서 PH2는 out-of-band artifact를 만들었다.

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

## 남은 한계

이 단계는 durable queue를 구현하지 않는다. queue-first architecture를 도입하려면 `ACCEPTED`와 `COMPLETED`를 분리하고, consumer idempotency, replay, DLQ, operator visibility까지 다시 설계해야 한다.

현재 PH1/PH2의 목표는 DB write 불가능 상황에서 성공을 거짓으로 말하지 않고, 동시에 장애 evidence를 DB 밖에 안전하게 남기는 것이다.
