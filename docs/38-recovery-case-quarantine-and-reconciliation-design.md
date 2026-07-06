# Recovery Case, Quarantine, and Reconciliation Design

> 잘못된 상태를 차단한 뒤에는 끝이 아니라 복구 case로 관리해야 한다.
> 차단, 격리, 분석, 승인, 보정, 검증, 사후 기록까지 하나의 lifecycle로 다룬다.

## 1. 왜 차단 이후 recovery case가 필요한가

금융 이벤트 시스템에서 단순 실패보다 어려운 상태는 처리 여부가 불명확한 상태다.

```text
요청은 들어왔다.
어딘가까지 처리한 것 같다.
응답은 실패했다.
이 거래를 재처리해도 되는가?
```

잘못된 상태를 차단하는 것만으로는 운영 복구가 끝나지 않는다.
affected account/client/event를 격리하고, 어떤 table에 어떤 흔적이 남았는지 분석한 뒤, 자동 복구 가능한지 또는 사람이 승인해야 하는지 결정해야 한다.

## 2. Recovery case lifecycle

```text
invalid state / balance mismatch / orphan idempotency 탐지
-> affected account 또는 client quarantine
-> recovery_case 생성
-> 자동 분석
-> proposed_action 생성
-> 사람 승인
-> 보정/재처리 실행
-> reconciliation 재실행
-> postmortem 기록
```

| 상태 | 의미 | 다음 단계 |
| --- | --- | --- |
| OPEN | 탐지 직후 case 생성 | evidence 수집 |
| AUTO_ANALYZED | 자동 분석 완료 | proposed action 검토 |
| WAITING_APPROVAL | 금전 상태 변경 가능성이 있어 승인 대기 | 운영자 승인 |
| APPROVED | 승인 완료 | 실행 job 대기 |
| EXECUTED | 복구 action 실행 | reconciliation 재검증 |
| REJECTED | 제안 action 반려 | 재분석 또는 수동 처리 |
| CLOSED | reconciliation 통과 후 종료 | postmortem 연결 |

## 3. Account/client/event quarantine 정책

| Quarantine 대상 | 적용 조건 | 차단 범위 | 해제 조건 |
| --- | --- | --- | --- |
| Account | balance mismatch, duplicate ledger, in-doubt event | 해당 account write 제한 | reconciliation PASS, recovery case CLOSED |
| Client/Partner | partner secret leak, 대량 invalid event | 해당 client write 제한 | secret rotation, replay risk 해소 |
| Event | stale PROCESSING, orphan idempotency | 해당 event 재처리 제한 | 자동 완료/실패 또는 수동 승인 |

Quarantine은 전체 write suspend보다 좁은 containment 방식이다.
정합성 위험이 전체 시스템으로 번질 가능성이 있으면 `WRITE_SUSPENDED`를 우선한다.

## 4. Stale PROCESSING 처리 기준

추가 상태 후보:

| 상태 | 의미 | 자동 처리 | 수동 처리 |
| --- | --- | --- | --- |
| FAILED_RETRYABLE | DB connection 문제, timeout 등 재시도 가능 실패 | 동일 key/body 재시도 허용 | 필요 없음 |
| FAILED_FINAL | 유효성 오류, 잔액 부족, 잘못된 signature | 동일 실패 replay | 정책 변경 시 검토 |
| STALE_PROCESSING | locked_until 이후에도 처리 중으로 남음 | ledger/event 존재 여부 자동 확인 | 일부 반영 흔적 있으면 수동 |
| RECOVERY_REQUIRED | 자동 판단 불가 | 신규 처리 차단 | 운영자 승인 |
| QUARANTINED | 정합성 위험 이벤트/계좌 격리 | 해당 범위 제한 | 복구 방식 승인 |
| RECONCILED | 검증 후 정상화 완료 | 재처리 금지 | 사후 기록 |

## 5. Reconciliation 기준

복구 전후 다음 결과가 모두 0이어야 한다.

- duplicate `transaction_events.external_event_id`
- duplicate `ledger_entries.transaction_event_id`
- ledger/account balance mismatch
- orphan ledger
- orphan idempotency
- invalid terminal status transition
- stale `PROCESSING` without recovery case

SQLite 기반 빠른 테스트는 회귀 확인에 사용할 수 있지만, row lock, concurrent unique conflict, failover in-doubt 상태는 PostgreSQL 기반 drill에서 별도 검증해야 한다.

## 6. 자동 재처리 가능 조건

다음 조건을 모두 만족하면 자동 재처리 후보가 될 수 있다.

- `transaction_event` 없음
- `ledger_entry` 없음
- `idempotency_records.status = FAILED_RETRYABLE`
- `request_hash` 동일
- external system이 같은 `Idempotency-Key`와 body로 재시도
- 장애 원인이 commit 전 DB connection 실패로 분류됨

자동 재처리는 idempotency와 unique constraint를 다시 통과해야 한다.

## 7. 자동 완료 처리 가능 조건

다음 조건을 모두 만족하면 자동 완료 처리 후보가 될 수 있다.

- `transaction_event` 존재
- `ledger_entry` 존재
- `account.balance`와 ledger 합계 일치
- `idempotency_records.request_hash` 동일
- terminal status가 state machine과 일치
- response replay에 필요한 결과를 재구성할 수 있음

자동 완료는 commit 후 응답 실패를 복구하는 용도다.

## 8. 수동 승인이 필요한 조건

다음 조건은 recovery case와 운영자 승인을 요구한다.

- balance mismatch
- duplicate ledger
- orphan idempotency
- failover 직후 in-doubt 상태
- ledger 일부 반영 흔적 존재
- status history와 current status 불일치
- compensation ledger가 필요한 금전 보정
- 고객/제휴사 영향도 판단이 필요한 경우

## 9. Compensation ledger vs direct update trade-off

- 선택한 정책: 금전 보정은 direct `UPDATE accounts.balance`보다 compensation ledger를 우선한다.
- 대안: 운영자가 직접 balance를 UPDATE한다.
- 선택 이유: LedgerEntry는 balance 변경의 이유/source이며, 보정 거래도 감사 추적 가능해야 한다.
- 포기한 것: 단순한 수동 수정 속도.
- 보완 전략: recovery case approval과 reconciliation을 통해 compensation event를 추적한다.
- 면접 답변용 한 문장: 금융 데이터는 잘못된 값을 덮어쓰기보다 반대 방향 ledger로 보정해야 감사 가능성과 재현성을 유지할 수 있습니다.

## 10. Recovery case 테이블 초안

```text
recovery_cases
- id
- case_type
  -- STALE_PROCESSING, BALANCE_MISMATCH, DUPLICATE_LEDGER, ORPHAN_IDEMPOTENCY, FAILOVER_IN_DOUBT
- severity
- account_id
- transaction_event_id
- idempotency_key_hash
- external_event_id
- detected_by
  -- scheduled_reconciliation, incident_analyzer, manual, ci_gate
- detected_at
- current_status
  -- OPEN, AUTO_ANALYZED, WAITING_APPROVAL, APPROVED, EXECUTED, REJECTED, CLOSED
- proposed_action
  -- MARK_COMPLETED, MARK_FAILED_RETRYABLE, COMPENSATE_LEDGER, REPLAY_EVENT, NOOP
- approval_required
- approved_by
- approved_at
- executed_at
- evidence_path
- before_snapshot_hash
- after_snapshot_hash
```

이번 문서는 설계 초안이며, 실제 migration은 후속 구현 Phase에서 별도로 다룬다.

## 11. Incident events 테이블 초안

```text
incident_events
- id
- incident_id
- severity
- scenario
  -- POSTGRES_DOWN, DB_POOL_EXHAUSTED, CONSISTENCY_VIOLATION, REDIS_DOWN, NGINX_5XX
- started_at
- detected_at
- mitigated_at
- recovered_at
- status
- primary_signal
- affected_routes
- affected_clients
- write_suspended
- auto_actions_json
- manual_actions_json
- report_path
```

## 12. Trade-off

### 12.1 자동 재처리 vs 수동 복구

- 선택한 정책: commit 전 실패가 확실하고 반영 흔적이 없을 때만 자동 재처리한다.
- 대안: 모든 stale PROCESSING을 운영자가 수동 처리한다.
- 선택 이유: 명확한 retryable 실패는 운영 부담을 줄일 수 있다.
- 포기한 것: 모든 케이스를 완전히 보수적으로 처리하는 단순성.
- 보완 전략: ledger/event/account 흔적이 있으면 recovery case로 전환한다.
- 면접 답변용 한 문장: 자동 재처리는 DB 반영 흔적이 없는 retryable 실패로 한정하고, 금전 흔적이 보이면 수동 승인으로 넘겼습니다.

### 12.2 quarantine vs 전체 write suspend

- 선택한 정책: 영향 범위가 특정 account/client로 제한되면 quarantine을 우선한다.
- 대안: 모든 정합성 의심 상황에서 전체 write suspend를 적용한다.
- 선택 이유: 전체 서비스 중단 없이 사고 범위를 제한할 수 있다.
- 포기한 것: containment 판단 로직의 복잡도.
- 보완 전략: 영향 범위가 불명확하거나 전역 제약 위반이면 전체 write suspend로 승격한다.
- 면접 답변용 한 문장: 특정 계좌 문제는 quarantine으로 제한하고, 전역 정합성 위험은 write suspend로 승격하는 2단계 containment를 설계했습니다.

### 12.3 compensation ledger vs direct UPDATE

- 선택한 정책: compensation ledger를 우선한다.
- 대안: direct UPDATE로 balance를 수정한다.
- 선택 이유: 감사 추적과 재현 가능한 reconciliation을 유지한다.
- 포기한 것: 빠른 수동 수정.
- 보완 전략: compensation event type과 recovery case evidence를 함께 저장한다.
- 면접 답변용 한 문장: balance는 ledger의 결과여야 하므로 보정도 ledger로 남기는 편이 금융 도메인에 맞습니다.

### 12.4 stale PROCESSING 자동 복구 vs recovery case 생성

- 선택한 정책: 자동 완료/재처리 조건을 만족하지 않으면 recovery case를 생성한다.
- 대안: locked_until 만료 시 모두 실패 처리한다.
- 선택 이유: 처리 중 일부 반영된 거래를 실패로 단정하면 중복 처리 위험이 생긴다.
- 포기한 것: 단순 timeout 기반 정리.
- 보완 전략: event/ledger/account/idempotency 상태를 비교해 action을 결정한다.
- 면접 답변용 한 문장: PROCESSING timeout만 보고 실패 처리하지 않고, DB 흔적을 대조한 뒤 자동 복구와 수동 승인을 분리했습니다.

## 13. 후속 구현 Phase 분리

이번 브랜치에서는 구현하지 않는다.
후속 구현 후보:

- `recovery_cases` migration과 repository
- stale PROCESSING detector
- reconciliation job 확장
- quarantine policy service
- recovery approval admin endpoint
- compensation ledger 생성 workflow
- sanitized recovery report generator
