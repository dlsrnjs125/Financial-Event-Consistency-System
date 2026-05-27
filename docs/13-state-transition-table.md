# 13. State Transition Table

## 1. 목적

이 문서는 거래 이벤트 상태 머신 구현의 기준이 되는 상태 전이표를 정의한다.

상태 전이는 거래 중복 처리, CANCEL 정책, 배포 전 테스트의 핵심 기준이므로 구현 전에 허용 경로와 금지 경로를 명확히 고정한다.

---

## 2. 상태 정의

| status | description |
|--------|-------------|
| `RECEIVED` | 외부 시스템으로부터 이벤트를 수신한 상태 |
| `VALIDATED` | 필드, 인증, 도메인 검증이 완료된 상태 |
| `PROCESSING` | DB Transaction 안에서 Ledger와 잔액 반영을 처리 중인 상태 |
| `COMPLETED` | Ledger 생성과 잔액 반영이 완료된 상태 |
| `SETTLED` | 외부 시스템과 정산까지 완료된 상태 |
| `FAILED` | 검증 또는 처리 실패 상태 |
| `CANCELLED` | 정산 전 취소가 완료된 상태 |

---

## 3. 상태 전이표

| current_status | next_status | allowed | reason |
|----------------|-------------|---------|--------|
| `RECEIVED` | `VALIDATED` | O | 기본 검증 성공 |
| `RECEIVED` | `FAILED` | O | 형식 오류 또는 인증 실패 |
| `VALIDATED` | `PROCESSING` | O | 처리 시작 |
| `VALIDATED` | `FAILED` | O | 도메인 검증 실패 |
| `PROCESSING` | `COMPLETED` | O | 원장 반영 성공 |
| `PROCESSING` | `FAILED` | O | 처리 실패 |
| `COMPLETED` | `SETTLED` | O | 정산 완료 |
| `COMPLETED` | `CANCELLED` | O | 정산 전 취소 |
| `SETTLED` | `CANCELLED` | X | 정산 후 단순 취소 금지 |
| `FAILED` | `COMPLETED` | X | 실패 거래 성공 처리 금지 |
| `COMPLETED` | `PROCESSING` | X | 완료 거래 재처리 금지 |
| `RECEIVED` | `COMPLETED` | X | 검증 단계 생략 금지 |
| `CANCELLED` | `COMPLETED` | X | 취소 거래 복구 금지 |
| `SETTLED` | `PROCESSING` | X | 정산 완료 거래 재처리 금지 |

---

## 4. CANCEL 정책과의 연결

- `COMPLETED` 상태의 거래는 정산 전이면 `CANCELLED`로 전이할 수 있다.
- `SETTLED` 상태의 거래는 `CANCELLED`로 직접 전이할 수 없다.
- `SETTLED` 이후 취소가 필요하면 `REVERSAL` 이벤트를 별도 정책으로 도입한다.
- CANCEL은 원거래 삭제가 아니라 반대 방향 LedgerEntry 생성으로 처리한다.

상세 정책은 [10-cancel-event-policy.md](10-cancel-event-policy.md)에 정리한다.

---

## 5. 구현 기준

상태 머신 구현은 다음 규칙을 따른다.

1. 전이는 명시적으로 허용된 경로만 가능하다.
2. 금지된 전이는 예외를 발생시킨다.
3. 상태 변경은 `event_state_histories`에 append-only로 기록한다.
4. 상태 변경과 Ledger 생성은 같은 DB Transaction 안에서 처리한다.
5. 상태 전이 테스트는 이 문서의 전이표를 기준으로 작성한다.

---

## 6. 설계 결론

상태 머신은 거래 이벤트가 잘못된 순서로 처리되거나 완료된 거래가 재처리되는 것을 막는 도메인 방어선이다.

이 문서의 전이표는 구현 코드, Unit Test, CI Gate의 기준으로 사용한다.
