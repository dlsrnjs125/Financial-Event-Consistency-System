# Write Suspend and Resume Runbook

## 1. 장애 상황

정합성 위험 또는 PostgreSQL write 불가 상태로 신규 금융 write path를 의도적으로 닫은 상태다.

Severity: SEV1 또는 SEV2

자동 조치:

- runtime write suspend flag 활성화 후보
- `write-suspend-state.json` artifact 기록
- Nginx write route blocking 후보
- incident report 초안 생성

수동 승인 필요 여부: resume에는 반드시 필요

승인자: 운영 책임자 또는 incident commander

Evidence 경로:

```text
reports/incidents/{incident_id}/write-suspend-state.json
reports/runtime/write-suspend-state.json
reports/production-hardening/ph1-write-suspend/{run_id}/report.md
```

## 2. 예상 원인

- PostgreSQL down 또는 failover
- consistency violation
- duplicate ledger 탐지
- account balance mismatch
- secret leak으로 인한 partner traffic 차단

## 3. 사용자 영향

- 신규 거래 이벤트 `503` 또는 정책에 따라 `409`
- 조회와 admin recovery는 제한적으로 허용 가능

## 4. 탐지 방법

- write suspend flag/status
- incident analyzer report
- consistency SQL result
- SLO/SLI SEV1 signal

## 5. 대응 방법

1. suspend 사유와 시작 시각을 incident report에 기록한다.
2. affected account/client/event 범위를 확인한다.
3. consistency SQL과 recovery case 목록을 확인한다.
4. 자동 복구 가능한 stale PROCESSING을 처리한다.
5. 수동 승인이 필요한 case는 승인 전까지 quarantine을 유지한다.

PH1 명령:

```bash
make ph1-write-suspend-status
WRITE_SUSPEND_STATE_FILE=reports/runtime/write-suspend-state.json \
  python3 scripts/write_suspend_state.py enable --reason postgres_unavailable
make ph1-write-suspend-resume
```

DB-down drill:

```bash
make ph1-db-down-drill
make ph2-db-down-incident-artifact
make ph3-db-down-incident-analysis
```

drill은 PostgreSQL stop, readiness failure, write `503` + `Retry-After`, operator resume, 복구 후 consistency count를 확인하고 `reports/production-hardening/ph1-write-suspend/{run_id}/report.md`에 evidence를 남긴다.
PH2 target은 같은 흐름 뒤에 `reports/incidents/{incident_id}/` sanitized artifact bundle과 `sanitized-report.md`를 생성하고 검증한다.
PH3 target은 같은 artifact를 rule-based analyzer로 분류하고 `analyzer-result.json`, `incident-analysis.md`를 생성한다.

## 6. Resume 승인 기준

- PostgreSQL write readiness 정상
- duplicate ledger/event 0
- account balance mismatch 0
- unresolved SEV1 recovery case 없음 또는 격리 완료
- 운영자 승인자와 승인 시각 기록 존재

PH1에서는 resume이 자동 실행되지 않는다.
PostgreSQL readiness와 duplicate event/ledger count를 확인한 뒤 운영자가 명시적으로 resume한다.
PH2 report는 resume 승인 전 검토할 evidence 초안이며, write resume 자체를 자동 승인하지 않는다.
PH3 analyzer result도 resume 승인 후보를 정리할 뿐이며, write resume 자동 승인은 수행하지 않는다.

## 7. Rollback/abort 조건

- resume 직후 5xx/503 재증가
- consistency SQL 실패
- unresolved recovery case가 새로 발견됨
- DB primary identity 또는 failover 상태 불명확

## 8. Postmortem 연결

- suspend 시작/종료 시각
- 승인자와 승인 시각
- write 차단 대상 route
- recovery case와 reconciliation 결과

## 9. 재발 방지

- write suspend trigger threshold 조정
- incident analyzer rule 보강
- recovery case evidence 누락 보완

## 10. README/블로그 기록 문장

Write suspend는 장애를 성공으로 위장하지 않기 위한 운영 상태이며, write resume은 정합성 evidence와 운영자 승인 후 수행한다.
