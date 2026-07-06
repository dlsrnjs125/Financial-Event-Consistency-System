# PostgreSQL 장애 중에도 장애 증거를 남기려면 어디에 기록해야 할까

## 1. 문제 상황

PostgreSQL은 이 시스템의 최종 Source of Truth다.
하지만 PostgreSQL이 down된 순간에는 `incident_events`나 `recovery_cases` 같은 DB table에 장애 정보를 즉시 저장할 수 없다.

PH1에서는 이 상황에서 신규 금융 write를 성공으로 응답하지 않도록 `503 Service Unavailable`과 `Retry-After`를 반환하는 write suspend 흐름을 구현했다.
PH2의 질문은 그 다음이다.

```text
DB가 죽었는데 장애 증거는 어디에 남길 것인가?
```

## 2. DB가 죽었는데 DB에 incident를 저장할 수 있을까?

저장할 수 없다.
정확히는, DB가 회복된 뒤 backfill할 수는 있지만 장애가 발생한 그 순간의 1차 evidence를 DB에만 의존하면 안 된다.

금융 write와 마찬가지로 incident 기록도 "기록했다고 주장하지만 실제로는 DB에 쓰이지 않은" 상태가 생길 수 있다.
따라서 PostgreSQL down window에서는 out-of-band artifact가 필요하다.

## 3. 선택한 방식: Out-of-band Artifact

PH2는 로컬 파일 시스템에 다음 구조를 만든다.

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

`manifest.json`은 incident id, scenario, severity candidate, confidence candidate, run id, evidence file 목록을 담는다.
`sanitized-report.md`는 운영자가 바로 읽을 수 있는 보고서 초안이다.

실제 incident analyzer나 recovery case DB 모델은 아직 만들지 않았다.
PH2는 후속 PH3/PH4가 사용할 수 있는 증거 묶음과 안전한 report skeleton까지만 구현한다.

## 4. Sanitized Report가 필요한 이유

장애 분석 자료는 AI 요약이나 외부 문서화로 이어질 수 있다.
그 과정에 원문 계좌번호, raw idempotency key, HMAC signature, Authorization header, raw request body가 섞이면 안 된다.

그래서 PH2 sanitizer는 denylist보다 보수적인 allowlist 방식을 사용한다.
허용된 key만 artifact에 남기고, 민감 key는 제거한다.
허용된 필드 안에 synthetic sensitive fixture와 같은 민감 값 패턴이 들어오면 `[REDACTED]`로 바꾼다.

## 5. 구현 구조

핵심 스크립트는 다음 파일이다.

```bash
scripts/ph2_incident_artifact.py
```

CLI는 세 가지 동작을 제공한다.

```bash
python scripts/ph2_incident_artifact.py create --scenario POSTGRES_DOWN --source manual
python scripts/ph2_incident_artifact.py sanitize --input /tmp/input.json --output /tmp/sanitized.json
python scripts/ph2_incident_artifact.py validate --latest
```

Makefile target은 운영 흐름에 맞춰 추가했다.

```bash
make ph2-incident-artifact
make ph2-incident-artifact-validate
make ph2-db-down-incident-artifact
make ops10-incident-artifact
```

## 6. PH1 DB Down Drill과 연결

`make ph2-db-down-incident-artifact`는 PH1 DB-down drill을 먼저 실행한다.
그 뒤 PH1 `RUN_ID`를 PH2 manifest에 연결하고, PH1 report에서 count-only consistency summary만 읽어온다.

중요한 제한은 다음과 같다.

- PH1 raw request body를 복사하지 않는다.
- raw header를 복사하지 않는다.
- raw idempotency key를 저장하지 않는다.
- HMAC signature를 저장하지 않는다.
- raw log 수집은 후속 기능으로 남긴다.

## 7. 트러블슈팅

개발 중 확인한 운영 주의사항:

- 실제 `reports/incidents/inc-*` artifact는 로컬 runtime evidence이므로 git에 commit하지 않는다.
- Docker가 없거나 stack이 떠 있지 않으면 Docker Compose status는 `not_collected`로 남긴다.
- `validate --latest`는 먼저 artifact가 생성되어 있어야 한다.
- 검증에서 민감 key가 발견되면 report를 손으로 고치기보다 생성 source에서 raw field를 제거해야 한다.

## 8. 검증 결과

이번 구현은 다음 테스트를 추가했다.

- sanitizer가 허용 필드를 유지하는지
- Authorization header, X-Signature, raw idempotency key, account number, DATABASE_URL 성격의 key를 제거하는지
- artifact 생성 시 manifest와 sanitized report가 만들어지는지
- `sensitive_data_included=false`가 기록되는지
- validate가 정상 artifact를 통과시키는지
- validate가 synthetic sensitive fixture가 들어간 artifact를 실패시키는지
- latest 옵션이 가장 최근 incident directory를 선택하는지

로컬 환경의 virtualenv Python 경로가 깨져 있으면 pytest 실행은 별도 환경 복구가 필요하다.
스크립트 자체는 system Python compile과 CLI create/validate로 우선 확인할 수 있다.

## 9. 남은 한계

PH2는 incident analyzer가 아니다.
severity와 confidence는 후보값이며 운영자 검토가 필요하다.

또한 PH2는 다음을 하지 않는다.

- DB-backed `incident_events` 생성
- `recovery_cases` 생성
- AI API 호출
- 자동 write resume 승인
- PostgreSQL HA 또는 durable queue 구성
- raw 로그 수집

## 10. 다음 단계

다음 구현 후보는 PH-Impl 3 Incident Analyzer MVP다.
PH2 artifact를 입력으로 받아 `/ready`, consistency summary, write suspend state 같은 신호를 deterministic rule로 묶고, 운영자가 검토할 incident classification draft를 만드는 단계다.
