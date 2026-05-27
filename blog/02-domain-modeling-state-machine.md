# 2편. 금융 거래 이벤트 도메인 모델링과 상태 머신 설계

## 들어가며

중복 처리 방지는 중요하지만, 그것만으로는 부족합니다.

**상태 머신**이 필요합니다.

왜냐하면 COMPLETED 상태인 거래가 갑자기 PROCESSING으로 돌아가면 안 되기 때문입니다.

---

## 핵심 엔티티

### 1. TransactionEvent (거래 이벤트)
외부 시스템에서 받은 이벤트 원본 데이터

```sql
CREATE TABLE transaction_events (
  id BIGSERIAL PRIMARY KEY,
  external_event_id VARCHAR(255) UNIQUE NOT NULL,  -- 외부 시스템의 이벤트 ID
  account_id VARCHAR(255) NOT NULL,                 -- 대상 계좌
  event_type VARCHAR(50) NOT NULL,                  -- DEPOSIT, WITHDRAW, CANCEL
  amount DECIMAL(18,2) NOT NULL,                    -- 거래 금액
  status VARCHAR(50) NOT NULL DEFAULT 'RECEIVED',   -- 상태
  occurred_at TIMESTAMP NOT NULL,                   -- 외부 시스템에서 발생 시각
  received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transaction_events_account_id ON transaction_events(account_id);
CREATE INDEX idx_transaction_events_status ON transaction_events(status);
```

### 2. Account (계좌)
```sql
CREATE TABLE accounts (
  id BIGSERIAL PRIMARY KEY,
  account_no VARCHAR(255) UNIQUE NOT NULL,
  balance DECIMAL(18,2) NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 3. LedgerEntry (원장 기록)
왜 잔액이 변했는가를 설명하는 기록

```sql
CREATE TABLE ledger_entries (
  id BIGSERIAL PRIMARY KEY,
  transaction_event_id BIGINT UNIQUE NOT NULL,      -- 하나의 이벤트는 정확히 1건의 장부 기록
  account_id BIGINT NOT NULL,
  event_type VARCHAR(50) NOT NULL,
  amount DECIMAL(18,2) NOT NULL,
  balance_after DECIMAL(18,2) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (transaction_event_id) REFERENCES transaction_events(id),
  FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE INDEX idx_ledger_entries_account_id ON ledger_entries(account_id);
```

### 4. IdempotencyRecord (멱등성 기록)
```sql
CREATE TABLE idempotency_records (
  id BIGSERIAL PRIMARY KEY,
  idempotency_key VARCHAR(255) UNIQUE NOT NULL,
  request_hash VARCHAR(64) NOT NULL,                -- SHA256(요청 body)
  status VARCHAR(50) NOT NULL,                      -- PROCESSING, COMPLETED, FAILED
  response_body JSONB NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP
);
```

### 5. EventStateHistory (상태 이력)
```sql
CREATE TABLE event_state_histories (
  id BIGSERIAL PRIMARY KEY,
  transaction_event_id BIGINT NOT NULL,
  old_status VARCHAR(50),
  new_status VARCHAR(50) NOT NULL,
  reason VARCHAR(255),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (transaction_event_id) REFERENCES transaction_events(id)
);

CREATE INDEX idx_event_state_histories_event_id ON event_state_histories(transaction_event_id);
```

---

## 상태 머신 설계

### 상태 정의
```
RECEIVED      → 외부 시스템에서 받은 초기 상태
VALIDATED     → 기본 검증 완료 (금액, 계좌 존재 여부 등)
PROCESSING    → 처리 중
COMPLETED     → 처리 성공 (장부에 기록됨)
SETTLED       → 정산 완료 (향후 확장)
FAILED        → 처리 실패
CANCELLED     → 취소됨
```

### 허용된 상태 전이
```
RECEIVED
  ↓
VALIDATED (검증 성공)
  ├─→ FAILED (검증 실패)
  │
  └─→ PROCESSING
       ├─→ COMPLETED (처리 성공)
       │    └─→ SETTLED (정산 완료)
       │
       └─→ FAILED (처리 실패)

CANCELLED ← 모든 상태에서 가능 (향후 확장)
```

### ❌ 금지된 상태 전이
```
COMPLETED → PROCESSING          ❌ (완료된 거래를 다시 처리)
FAILED → COMPLETED              ❌ (실패한 거래가 갑자기 성공)
SETTLED → CANCELLED             ❌ (정산 완료 후 단순 취소)
RECEIVED → COMPLETED            ❌ (검증 단계 생략)
PROCESSING → RECEIVED           ❌ (처리 중인 거래가 초기 상태로)
```

---

## 상태 머신 코드 (Python)

```python
from enum import Enum
from dataclasses import dataclass

class TransactionStatus(Enum):
    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class InvalidStateTransition(Exception):
    pass

@dataclass
class TransactionStateMachine:
    current_status: TransactionStatus
    
    # 각 상태에서 전이 가능한 다음 상태
    ALLOWED_TRANSITIONS = {
        TransactionStatus.RECEIVED: {
            TransactionStatus.VALIDATED,
            TransactionStatus.FAILED
        },
        TransactionStatus.VALIDATED: {
            TransactionStatus.PROCESSING,
            TransactionStatus.FAILED
        },
        TransactionStatus.PROCESSING: {
            TransactionStatus.COMPLETED,
            TransactionStatus.FAILED
        },
        TransactionStatus.COMPLETED: {
            TransactionStatus.SETTLED
        },
        TransactionStatus.SETTLED: {},  # 최종 상태
        TransactionStatus.FAILED: {},   # 최종 상태
        TransactionStatus.CANCELLED: {} # 최종 상태
    }
    
    def can_transition_to(self, next_status: TransactionStatus) -> bool:
        allowed = self.ALLOWED_TRANSITIONS.get(self.current_status, set())
        return next_status in allowed
    
    def transition_to(self, next_status: TransactionStatus, reason: str = None) -> None:
        if not self.can_transition_to(next_status):
            raise InvalidStateTransition(
                f"Cannot transition from {self.current_status.value} to {next_status.value}. "
                f"Allowed: {[s.value for s in self.ALLOWED_TRANSITIONS.get(self.current_status, set())]}"
            )
        self.current_status = next_status
```

---

## 테스트 예시

### 테스트 1: 완료된 거래는 재처리 불가
```python
def test_completed_event_cannot_go_back_to_processing():
    sm = TransactionStateMachine(TransactionStatus.COMPLETED)
    
    with pytest.raises(InvalidStateTransition):
        sm.transition_to(TransactionStatus.PROCESSING)
```

### 테스트 2: 정상 흐름
```python
def test_normal_transaction_flow():
    sm = TransactionStateMachine(TransactionStatus.RECEIVED)
    
    sm.transition_to(TransactionStatus.VALIDATED)
    assert sm.current_status == TransactionStatus.VALIDATED
    
    sm.transition_to(TransactionStatus.PROCESSING)
    assert sm.current_status == TransactionStatus.PROCESSING
    
    sm.transition_to(TransactionStatus.COMPLETED)
    assert sm.current_status == TransactionStatus.COMPLETED
```

---

## ERD (초안)

```
transaction_events
├── id (PK)
├── external_event_id (UNIQUE)
├── account_id
├── event_type
├── amount
├── status
├── occurred_at
└── created_at

accounts
├── id (PK)
├── account_no (UNIQUE)
├── balance
└── created_at

ledger_entries
├── id (PK)
├── transaction_event_id (UNIQUE, FK)
├── account_id (FK)
├── event_type
├── amount
├── balance_after
└── created_at

idempotency_records
├── id (PK)
├── idempotency_key (UNIQUE)
├── request_hash
├── status
├── response_body
└── created_at

event_state_histories
├── id (PK)
├── transaction_event_id (FK)
├── old_status
├── new_status
├── reason
└── created_at
```

---

## 핵심 메시지

> **금융 이벤트는 CRUD가 아니라 상태 전이의 문제다. 명시적 상태 머신으로 불가능한 전이를 차단하면, 장애 상황이나 재시도 상황에서 거래가 의도하지 않은 상태로 변경되는 것을 방지할 수 있다.**

---

## 다음 편에서

3편에서는 Idempotency Key로 어떻게 중복 요청을 방어하는지, 그리고 같은 키로 다른 요청이 오는 상황까지 다룹니다.
