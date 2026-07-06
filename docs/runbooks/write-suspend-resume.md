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

## 6. Resume 승인 기준

- PostgreSQL write readiness 정상
- duplicate ledger/event 0
- account balance mismatch 0
- unresolved SEV1 recovery case 없음 또는 격리 완료
- 운영자 승인자와 승인 시각 기록 존재

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
