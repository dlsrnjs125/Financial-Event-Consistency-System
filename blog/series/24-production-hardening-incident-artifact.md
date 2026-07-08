# PostgreSQL 장애 중에도 증거를 남기려면 어디에 기록해야 할까

PostgreSQL은 이 시스템의 최종 Source of Truth다. 그런데 PostgreSQL이 죽은 순간, incident evidence를 PostgreSQL에만 저장하려고 하면 이상한 모순이 생긴다.

이 글의 질문은 단순하다.

```text
DB가 down된 순간에도 장애 증거를 남겨야 한다면, 그 증거는 어디에 남겨야 하는가?
```

## DB가 Source of Truth일 때 생기는 역설

금융 write path에서는 PostgreSQL commit이 처리 완료의 근거다. 그래서 PH1에서는 PostgreSQL write path가 불가능할 때 신규 금융 write를 성공으로 응답하지 않고 `503 + Retry-After`로 fail-closed 처리했다.

하지만 incident evidence는 조금 다르다. DB가 죽었다는 사실을 DB에만 기록하려고 하면, 장애 순간의 1차 증거가 사라질 수 있다. DB가 회복된 뒤 backfill할 수는 있어도, 장애 중에 어떤 상태였는지 남기는 경로가 별도로 필요했다.

## DB에 쓰지 못하는 순간에도 evidence는 필요하다

PH2에서는 DB-backed incident model을 바로 만들지 않았다. 대신 out-of-band artifact를 먼저 만들었다.

```text
reports/incidents/{incident_id}/
  manifest.json
  sanitized-report.md
  write-suspend-state.json
  health-ready-summary.json
  docker-compose-status.txt
  consistency-summary.json
  command-results.json
  raw/
    README.md
```

핵심은 artifact를 "복구 실행 기록"이 아니라 "장애 중 수집 가능한 sanitized evidence bundle"로 제한한 점이다. PH2는 incident DB 모델이나 자동 복구를 완성했다고 주장하지 않는다.

## Sanitized report를 먼저 만든 이유

장애 증거는 AI 요약, postmortem, 운영 공유 문서로 이어질 수 있다. 그 경로에 원문 금융 식별자, retry 식별자, 인증/서명 자료, 요청 본문이 섞이면 incident artifact 자체가 유출 경로가 된다.

그래서 PH2는 sanitizer를 먼저 두었다. 허용된 key만 남기고, 민감 key나 민감 text pattern은 제거하거나 redaction한다. report에는 `sensitive_data_included=false`를 명시해 다음 단계의 analyzer가 안전하게 읽을 수 있는지 확인하게 했다.

## PH1 DB-down drill과 연결한 부분

PH2는 PH1과 연결된다. PH1이 DB down 중 신규 write를 막았다면, PH2는 같은 흐름에서 evidence를 남긴다.

```bash
make ph2-db-down-incident-artifact
```

이 target은 PH1 DB-down drill 결과와 PH2 artifact를 연결하되, raw request나 인증 자료를 복사하지 않는다. consistency summary도 count-only 형태로만 가져온다.

## 개발 중 실제로 막힌 지점

가장 중요한 트러블슈팅은 손상된 `write-suspend-state.json`이었다. 장애 중 생성된 state file이 중단이나 수동 수정으로 깨질 수 있는데, 이때 artifact 생성 자체가 실패하면 PH2의 목적이 무너진다.

수정 후에는 state file JSON parse가 실패해도 artifact 생성을 멈추지 않고 `invalid_state_json` summary를 남긴다. 장애 증거 수집은 장애 상황에서도 실패하지 않는 쪽이 맞다고 판단했다.

또 하나는 incident id 충돌이었다. 같은 초에 같은 scenario로 artifact를 만들 수 있으므로 suffix를 붙여 충돌을 피하게 했다. 이것은 운영 빈도보다 반복 테스트 안정성 때문에 필요했다.

## 검증한 것

PH2 테스트는 sanitizer가 허용 필드를 유지하고 민감 key/text를 제거하는지, artifact 생성과 validation이 통과하는지, 손상된 write suspend state를 안전한 summary로 남기는지 확인한다.

Docker Compose status가 수집되지 않아도 artifact 전체를 무효화하지 않는다. DB down 중에는 일부 evidence가 `not_collected`일 수 있고, 그것도 장애 증거의 일부다.

## PH2에서 확정한 운영 경계

PH2에서 확정한 것은 DB down 중에도 DB에 의존하지 않는 sanitized incident evidence를 남기는 구조다.

반대로 incident DB 모델, 자동 복구, write resume 승인, raw log 수집은 이 단계의 범위가 아니다. PH2는 다음 단계가 믿고 읽을 수 있는 안전한 evidence bundle을 만드는 단계로 남겼다.
