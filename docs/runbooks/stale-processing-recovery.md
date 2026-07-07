# Stale PROCESSING Recovery Runbook

## 1. 장애 상황

`PROCESSING` 상태의 idempotency/event record가 `locked_until` 이후에도 완료 또는 실패로 전이되지 않은 상태다.

Severity: 단일 event는 SEV2, 다수 event 또는 failover window는 SEV1

자동 조치:

- stale PROCESSING 후보 탐지
- event/ledger/account/idempotency 대조
- 자동 완료, 자동 재처리, recovery case 생성 중 하나로 분기

PH5 기준에서는 stale PROCESSING detector와 count-only reconciliation job이 구현되어 있다.
탐지 결과는 recovery case로 연결되지만, 자동 완료/실패 처리나 금전 보정은 실행하지 않는다.

수동 승인 필요 여부: 일부 반영 흔적 또는 in-doubt 상태에서는 필요

승인자: 운영 책임자

Evidence 경로:

```text
reports/reconciliation/{run_id}/
```

PH5 운영 명령:

```bash
make ph5-detect-stale-processing
make ph5-reconcile
make ph5-reconciliation-run
make ph5-reconciliation-validate
```

## 2. 예상 원인

- API process restart
- DB connection timeout
- commit 후 응답 실패
- failover 중 stale connection
- background cleanup 누락

## 3. 사용자 영향

- 동일 idempotency key 재시도 시 pending 또는 already processing으로 보일 수 있음
- 자동 판단 불가 시 affected event/account quarantine 가능

## 4. 탐지 방법

- stale PROCESSING detector
- idempotency locked_until 만료
- transaction_event/ledger_entry 존재 여부 비교
- consistency SQL의 stale processing count

## 5. 대응 방법

1. request_hash가 같은지 확인한다.
2. transaction_event 존재 여부를 확인한다.
3. ledger_entry 존재 여부를 확인한다.
4. account balance와 ledger 합계를 비교한다.
5. 자동 재처리, 자동 완료, recovery case 생성 중 하나로 분기한다.

## 6. 분기 기준

| 조건 | 처리 |
| --- | --- |
| event 없음, ledger 없음, FAILED_RETRYABLE로 판단 가능 | 자동 재처리 후보 |
| event 있음, ledger 있음, balance 일치 | 자동 완료 후보 |
| ledger 일부 흔적, balance mismatch, failover in-doubt | recovery case 생성 |

## 7. 복구 검증

- stale PROCESSING count 감소
- duplicate ledger 0
- account balance mismatch 0
- unresolved recovery case 확인

## 8. Rollback/abort 조건

- ledger 일부 반영 흔적이 있는데 자동 실패 처리하려는 경우
- event/ledger/account 대조 결과가 불일치함
- 동일 recovery action 재실행 guard가 없음
- failover in-doubt window가 닫히지 않음

## 9. Postmortem 연결

- stale record count
- 자동 완료/자동 재처리/recovery case 분기 결과
- affected account/client/event
- retry contract 위반 여부

## 10. 재발 방지

- locked_until 기준 조정
- timeout/retry policy 문서화
- stale detector threshold 운영값 조정
- recovery case 처리 후 reconciliation 재실행 기준 문서화

## 11. README/블로그 기록 문장

Stale PROCESSING은 timeout만 보고 실패 처리하지 않고, event/ledger/account/idempotency 상태를 대조해 자동 복구와 수동 승인을 분리한다.
