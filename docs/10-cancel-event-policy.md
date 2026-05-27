# 10. CANCEL Event Policy

## 1. CANCEL 정책이 필요한 이유

거래 취소는 단순히 기존 거래를 삭제하는 작업이 아니다.

금융 시스템에서는 이미 발생한 거래 기록을 삭제하면 감사 추적이 불가능해진다.

따라서 CANCEL 이벤트는 원거래를 삭제하지 않고, 원거래와 반대 방향의 LedgerEntry를 생성하는 방식으로 처리한다.

---

## 2. 기본 정책

```text
1. 원거래는 삭제하지 않는다.
2. 원거래의 반대 방향 LedgerEntry를 생성한다.
3. 원거래 상태는 CANCELLED로 변경한다.
4. 이미 SETTLED 된 거래는 단순 CANCEL을 허용하지 않는다.
5. SETTLED 이후 취소는 REVERSAL 이벤트로 별도 처리한다.
```

---

## 3. 예시

### 입금 취소

```text
DEPOSIT 10,000
-> LedgerEntry +10,000

CANCEL DEPOSIT 10,000
-> LedgerEntry -10,000
-> 원거래 상태 CANCELLED
```

### 출금 취소

```text
WITHDRAW 10,000
-> LedgerEntry -10,000

CANCEL WITHDRAW 10,000
-> LedgerEntry +10,000
-> 원거래 상태 CANCELLED
```

---

## 4. 금지 정책

- 원거래 row 삭제 금지
- LedgerEntry 삭제 금지
- COMPLETED 거래를 다시 PROCESSING으로 변경 금지
- SETTLED 거래를 CANCELLED로 직접 변경 금지

---

## 5. 설계 결론

CANCEL은 데이터 삭제가 아니라 보정 거래 생성으로 처리한다.

이를 통해 거래 이력을 유지하면서도 잔액을 원래 상태로 되돌릴 수 있다.

## 6. Phase 5 구현 기준

Phase 5에서는 별도 `original_event_id` FK 컬럼을 추가하지 않고, 요청 Body의 `original_external_event_id`로 원거래를 조회해 CANCEL을 처리한다.
PostgreSQL 운영 기준에서는 원거래를 `SELECT FOR UPDATE`로 조회해 동시 CANCEL이 같은 원거래를 중복 보정하지 못하도록 한다.

검증 기준은 다음과 같다.

- `original_external_event_id`는 CANCEL 요청에서 필수다.
- 원거래 account, amount, currency가 CANCEL 요청과 일치해야 한다.
- 원거래 event_type은 `DEPOSIT` 또는 `WITHDRAW`여야 한다.
- 원거래 status는 `COMPLETED`여야 한다.
- `SETTLED` 원거래는 CANCEL할 수 없다.
- 이미 `CANCELLED`인 원거래는 다시 CANCEL할 수 없다.

Phase 5의 한계는 CANCEL 이벤트 row만 보고 원거래를 DB-level FK로 직접 추적하기 어렵다는 점이다.
후속 보완으로 `transaction_events.original_event_id` nullable FK 추가 여부를 검토한다.
