# Consistency Violation Runbook

## 1. 장애 정의

ledger 중복 반영, account balance 불일치, 잘못된 terminal status 전이, orphan idempotency record가 발견된 상태다.

금융 정합성 위반은 error budget을 허용하지 않으며 SEV1으로 분류한다.

## 2. 사용자 영향

- 계좌 잔액 불일치
- 중복 입금/출금 가능성
- 거래 상태 신뢰도 하락
- 수동 reconciliation 필요 가능성

## 3. 즉시 확인할 Dashboard

- API dashboard: duplicate/conflict/error metric
- PostgreSQL dashboard: transaction rollback, deadlock, lock wait
- Consistency report: ledger/account/idempotency 검증 결과

## 4. Alert Rule

```yaml
annotations:
  runbook: "docs/runbooks/consistency-violation.md"
```

확인할 alert:

- `FinancialConsistencyViolation`
- `DuplicateLedgerDetected`
- `AccountBalanceMismatch`

## 5. 1차 확인 명령

```bash
make deploy-verify
make k6-verify
```

추가 SQL:

```sql
SELECT external_event_id, COUNT(*)
FROM ledger_entries
GROUP BY external_event_id
HAVING COUNT(*) > 1;
```

## 6. 원인 분기표

| 관측 결과 | 판단 | 대응 |
|---|---|---|
| ledger 중복 | unique 제약 또는 transaction 경계 문제 | 신규 처리 중단, DB 제약 확인 |
| balance 불일치 | ledger/account atomicity 문제 | account lock/transaction 확인 |
| orphan idempotency | 처리 중 실패 후 정리 누락 | idempotency record 복구 검토 |
| invalid transition | state machine 우회 | service layer 경로 확인 |

## 7. 대응 절차

1. 신규 write traffic을 제한하거나 rollback한다.
2. 정합성 검증 SQL을 실행한다.
3. 영향 account/event 범위를 산정한다.
4. 관련 trace_id/request_id/log를 수집한다.
5. 수동 보정이 필요하면 별도 승인 절차를 따른다.
6. 복구 후 동일 SQL을 재실행한다.

## 8. 복구 확인 기준

- duplicate ledger count 0
- account balance mismatch 0
- orphan idempotency count 0
- invalid transition 증가 중단

## 9. 재발 방지

- DB unique constraint 재검증
- transaction boundary 테스트 추가
- consistency test를 CI Gate에 추가/강화
- runbook과 alert threshold 업데이트

## 10. 사후 기록 템플릿

- 발생 시간:
- 영향 account/event 수:
- 정합성 위반 유형:
- 복구 방식:
- 재발 방지:
