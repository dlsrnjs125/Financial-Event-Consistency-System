# 27. 장애 이후 애매하게 남은 거래 상태는 어떻게 처리해야 할까

## 1. 문제 상황

DB 장애, timeout, 서버 중단 이후 가장 난감한 상태는 성공도 실패도 확정하기 어려운 거래다.
`idempotency_records.status=PROCESSING`이 오래 남아 있거나, transaction event와 ledger 사이에 어긋난 흔적이 생길 수 있다.

## 2. PROCESSING 상태가 오래 남는 이유

요청은 시작됐지만 응답 전에 프로세스가 죽거나 DB 연결이 끊기면 idempotency record가 처리 중으로 남을 수 있다.
외부 시스템은 timeout을 보고 같은 key로 재시도할 수 있지만, 내부에서는 일부 작업이 이미 진행됐을 수도 있다.

## 3. 자동 완료/실패 처리가 위험한 이유

ledger가 이미 생성됐는지, account balance가 맞는지, idempotency response를 복원할 수 있는지 확인하지 않고 상태를 바꾸면 중복 반영이나 잘못된 실패 replay로 이어질 수 있다.

## 4. 선택한 방식: Stale Detector + Reconciliation

PH5는 오래된 `PROCESSING` record를 찾고, duplicate ledger, orphan idempotency, event/ledger mismatch, balance mismatch를 count-only로 집계한다.
이 단계는 탐지와 evidence 생성만 담당한다.

## 5. Recovery Case와 연결

위험 후보는 PH4 recovery case로 연결된다.
같은 stale record나 reconciliation issue를 여러 번 탐지해도 `source_key` 기준으로 중복 case가 생기지 않는다.

## 6. Report Artifact

PH5는 `reports/reconciliation/{run_id}/` 아래에 summary JSON과 markdown report를 남긴다.
raw account number, raw idempotency key, request body, signature, Authorization header는 포함하지 않는다.

## 7. 트러블슈팅

DB가 내려간 상태에서는 PH5를 실행하지 않는다.
먼저 PH1 write suspend와 PH2/PH3 incident artifact flow로 증거를 남기고, DB가 복구된 뒤 PH5 reconciliation을 실행한다.

## 8. 검증 결과

이번 구현에서는 stale detector, recovery case idempotency, reconciliation count, report validation을 unit/integration test로 검증한다.
실제 운영 데이터 기반 reconciliation 결과는 환경 의존적이므로 sample만 repository에 보관한다.

## 9. 남은 한계

PH5는 자동 보정 단계가 아니다.
stale record 자동 완료/실패, compensation ledger 생성, balance correction은 수동 승인 이후 별도 구현 범위로 남긴다.

## 10. 다음 단계

다음 단계는 AI-safe context sanitizer다.
reconciliation evidence를 외부 분석 도구나 AI에 넘기기 전, 어떤 필드를 제거하고 어떤 요약만 허용할지 별도로 고정해야 한다.
