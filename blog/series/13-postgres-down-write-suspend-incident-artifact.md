# PostgreSQL이 죽었을 때 성공 응답도, 장애 기록 유실도 막고 싶었다

Redis down과 PostgreSQL down은 다르다. Redis는 보조 계층이지만 PostgreSQL은 최종 Source of Truth다. PostgreSQL write path가 불가능하면 신규 금융 write를 성공으로 응답할 근거가 없다.

## DB commit 근거가 없으면 COMPLETED를 말할 수 없다

PostgreSQL이 down된 상태에서 `200 OK`나 `COMPLETED`를 반환하면 외부 시스템은 거래가 끝났다고 믿는다. 하지만 내부에는 commit evidence가 없다.

그래서 PH1에서는 PostgreSQL write path 장애 시 `503 + Retry-After`로 fail-closed 처리했다.

```text
DB write unavailable
-> new financial write blocked
-> 503 Service Unavailable
-> Retry-After returned
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

그래서 JSON parse 실패를 fatal error로 보지 않고 `invalid_state_json` summary로 남겼다. 장애 기록기는 정상 상황에서만 동작하면 안 된다고 판단했다.
