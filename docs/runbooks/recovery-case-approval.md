# Recovery Case Approval Runbook

## 1. 장애 상황

자동 복구로 판단할 수 없는 stale PROCESSING, balance mismatch, duplicate ledger, failover in-doubt 이벤트가 recovery case로 등록된 상태다.

Severity: recovery case type에 따라 SEV1 또는 SEV2

자동 조치:

- affected account/client/event quarantine 후보 생성
- proposed_action 생성
- evidence path 연결

수동 승인 필요 여부: 필요

승인자: 운영 책임자, 보안 사고인 경우 보안 담당자 포함

Evidence 경로:

```text
reports/incidents/{incident_id}/pending-recovery-cases.json
```

## 2. 예상 원인

- commit 후 응답 실패
- failover 중 처리 여부 불명확
- transaction boundary bug
- state machine 우회
- 수동 데이터 수정 또는 migration 문제

## 3. 사용자 영향

- affected account/client/event write 제한
- 일부 거래 상태 확인 지연
- 수동 reconciliation 필요 가능성

## 4. 탐지 방법

- recovery case 목록
- consistency SQL count
- incident analyzer report
- structured log trace_id/event_id evidence

## 5. 승인 전 확인

1. before snapshot hash를 확인한다.
2. transaction_event, ledger_entry, account balance, idempotency record를 대조한다.
3. proposed_action이 자동 재처리, 자동 완료, compensation ledger, noop 중 무엇인지 확인한다.
4. raw account number, raw idempotency key, secret이 report에 없는지 확인한다.
5. 승인자와 승인 시각을 기록한다.

## 6. 복구 검증

- proposed_action 실행 결과 확인
- reconciliation 재실행
- after snapshot hash 기록
- recovery case CLOSED 처리
- postmortem action item 기록

## 7. Rollback/abort 조건

- 승인자와 실행자가 분리되지 않음
- before snapshot hash 누락
- compensation ledger idempotency key 또는 recovery_case_id unique guard 없음
- 실행 중 오류가 발생했지만 `EXECUTION_FAILED`로 기록되지 않음
- report에 raw sensitive data 포함

## 8. Postmortem 연결

- recovery_case_id
- 승인자/실행자/승인 시각/실행 시각
- before/after snapshot hash
- compensation ledger id 또는 noop 사유

## 9. 재발 방지

- 자동 분석 rule 보강
- state machine 또는 transaction boundary 테스트 추가
- runbook threshold 갱신

## 10. README/블로그 기록 문장

자동 판단이 불가능한 금전 상태는 recovery case로 격리하고, 보정 또는 재처리는 사람이 승인한 뒤 reconciliation으로 검증한다.
