# 금융 이벤트 정합성 시스템 - 정합성 규칙

## 개요

이 문서는 시스템이 **"정합성이 맞다"와 "정합성이 깨졌다"를 판단하는 기준**을 명시합니다.

개발 중 모든 테스트, CI/CD Gate, 배포 기준은 이 규칙을 따릅니다.

---

## 핵심 정합성 규칙

### 규칙 1️⃣ 동일 이벤트는 한 번만 반영된다

**명칭**: Single Event Processing (SEP)

**정의**:
```
동일한 external_event_id를 가진 이벤트가 N번 들어와도
transaction_event 테이블: 1건
ledger_entry 테이블: 1건
account.balance 변경: 1회
```

**예시**:
```
입금 이벤트 BANK-A-20260527-0001이 100번 들어옴
    ↓
- transaction_event 테이블 확인 → 1행만 존재 ✅
- ledger_entry 테이블 확인 → 1행만 존재 ✅
- account.balance 확인 → 원래 100,000 + 10,000 = 110,000 ✅
```

**검증 방법**:
```sql
-- transaction_event 테이블에서 external_event_id별 행 수
SELECT external_event_id, COUNT(*) as cnt
FROM transaction_events
GROUP BY external_event_id
HAVING COUNT(*) > 1;

-- 결과가 0이면 ✅ 합격
```

**테스트**:
```python
def test_same_external_event_processed_only_once():
    external_event_id = "BANK-A-20260527-0001"
    
    # 100번 요청 (동시)
    responses = [api.post_event(external_event_id) for _ in range(100)]
    
    # 검증
    assert db.count_transaction_events(external_event_id) == 1
    assert db.count_ledger_entries(external_event_id) == 1
    assert all(r.status == "COMPLETED" for r in responses)
```

---

### 규칙 2️⃣ Idempotency Key는 같은 응답을 반환한다

**명칭**: Idempotency Response Consistency (IRC)

**정의**:
```
동일한 Idempotency-Key 헤더로 같은 요청 Body가 N번 들어오면
모든 응답이 동일하고, 실제 처리는 1회만 발생
```

**예시**:
```
POST /api/v1/transaction-events
Idempotency-Key: idem-20260527-001
{
  "external_event_id": "BANK-A-0001",
  "amount": 10000
}

1차 요청 → HTTP 200 { "event_id": "evt-001", "balance_after": 110000 }
2차 요청 → HTTP 200 { "event_id": "evt-001", "balance_after": 110000 }  (동일 응답)
3차 요청 → HTTP 200 { "event_id": "evt-001", "balance_after": 110000 }  (동일 응답)

실제 처리: 1회만
```

**HTTP Status 기준**:

| 상황 | 상태 코드 | 응답 |
|-----|---------|-----|
| 첫 요청 | 200 OK | 신규 처리 결과 |
| 재요청 (처리 중) | 202 Accepted | 처리 상태 |
| 재요청 (완료) | 200 OK | 저장된 결과 |
| 재요청 (실패) | 원본 상태 | 저장된 에러 |

**검증 방법**:
```python
def test_same_idempotency_key_returns_same_response():
    idem_key = "idem-20260527-001"
    
    # 1차 요청
    resp1 = api.post_event(
        idempotency_key=idem_key,
        event_id="evt-001",
        amount=10000
    )
    
    # 2차 요청 (동일한 요청)
    resp2 = api.post_event(
        idempotency_key=idem_key,
        event_id="evt-001",
        amount=10000
    )
    
    # 검증
    assert resp1.json() == resp2.json()
    assert db.count_transaction_events("evt-001") == 1
```

---

### 규칙 3️⃣ 같은 Key로 다른 요청이 오면 거부한다

**명칭**: Idempotency Key Mutation Detection (IKMD)

**정의**:
```
동일한 Idempotency-Key를 사용하되,
요청 Body가 다르면 409 Conflict를 반환
```

**예시 - 금액이 다른 경우**:
```
1차 요청
POST /api/v1/transaction-events
Idempotency-Key: idem-20260527-001
{
  "amount": 10000
}
→ HTTP 200 ✅

2차 요청 (다른 금액!)
POST /api/v1/transaction-events
Idempotency-Key: idem-20260527-001
{
  "amount": 50000  ← 다르다!
}
→ HTTP 409 Conflict ❌
```

**검증 방법**:
```python
def test_same_key_with_different_body_returns_conflict():
    idem_key = "idem-20260527-001"
    
    # 1차 요청
    resp1 = api.post_event(
        idempotency_key=idem_key,
        amount=10000
    )
    assert resp1.status_code == 200
    
    # 2차 요청 (다른 금액)
    resp2 = api.post_event(
        idempotency_key=idem_key,
        amount=50000
    )
    assert resp2.status_code == 409
    assert "conflict" in resp2.json()["message"].lower()
```

**Request Hash 저장**:
```
idempotency_records 테이블
├─ idempotency_key: "idem-20260527-001"
├─ request_hash: SHA256(normalized_body) → "abc123..."
├─ response_body: {...}
└─ status: "COMPLETED"

새 요청이 오면:
1. Idempotency Key 조회
2. request_hash 비교
3. 다르면 → 409 Conflict
4. 같으면 → 저장된 response 반환
```

---

### 규칙 4️⃣ 잔액 변경은 Ledger 기준으로 추적 가능해야 한다

**명칭**: Ledger-Based Balance Integrity (LBBI)

**정의**:
```
Account.balance = (초기 잔액) + Σ(Ledger 거래액)

모든 잔액 변경의 원인이 Ledger에 기록되어야 하고,
Ledger를 통해 잔액을 재계산할 수 있어야 한다.
```

**예시**:
```
계좌 생성 (초기 잔액: 100,000)
    ↓
입금 이벤트 (10,000) → LedgerEntry { amount: +10,000 }
    ↓
출금 이벤트 (5,000)  → LedgerEntry { amount: -5,000 }
    ↓
현재 잔액: 100,000 + 10,000 - 5,000 = 105,000

Ledger 기준 잔액 재계산:
SELECT SUM(amount) FROM ledger_entries WHERE account_id = 1
Result: 5,000
Initial Balance: 100,000
Current Balance: 100,000 + 5,000 = 105,000 ✅
```

**검증 방법**:
```python
def test_ledger_based_balance_is_consistent():
    account_id = 1
    initial_balance = 100000
    
    # 여러 거래 실행
    api.deposit(account_id, 10000)
    api.withdraw(account_id, 5000)
    
    # 방법 1: Account 테이블에서 직접 조회
    account_balance = db.query(
        "SELECT balance FROM accounts WHERE account_id = %s",
        account_id
    )
    
    # 방법 2: Ledger 합계로 계산
    ledger_sum = db.query(
        "SELECT SUM(amount) FROM ledger_entries WHERE account_id = %s",
        account_id
    )
    calculated_balance = initial_balance + ledger_sum
    
    # 검증
    assert account_balance == calculated_balance
```

**제약조건**:
```sql
-- LedgerEntry와 TransactionEvent는 1:1 대응
ALTER TABLE ledger_entries
ADD UNIQUE (transaction_event_id);
```

---

### 규칙 5️⃣ 상태 전이는 허용된 경로만 가능하다

**명칭**: State Machine Enforcement (SME)

**정의**:
```
Transaction Event는 다음 상태만 허용하고,
허용되지 않는 전이는 예외 발생
```

**허용되는 상태 전이**:
```
RECEIVED
    ↓
VALIDATED
    ↓
PROCESSING
    ↓
COMPLETED
    ↓
SETTLED

또는 언제든 FAILED (에러 발생)
또는 특정 조건에서 CANCELLED
```

**상태 정의**:

| 상태 | 의미 | 설명 |
|-----|------|------|
| **RECEIVED** | 이벤트 수신 | 외부 시스템으로부터 이벤트 도착 |
| **VALIDATED** | 유효성 검증 | 필드, 금액, 계좌 존재 여부 확인 |
| **PROCESSING** | 처리 중 | Transaction 시작, Ledger 생성 중 |
| **COMPLETED** | 처리 완료 | Ledger 생성 완료, 잔액 반영 완료 |
| **SETTLED** | 정산 완료 | 외부 시스템과 정산 완료 |
| **FAILED** | 처리 실패 | 유효성 검증 실패 또는 Ledger 생성 실패 |
| **CANCELLED** | 취소됨 | CANCEL 이벤트로 인한 상태 |

**금지된 전이**:

| 전이 | 이유 | 결과 |
|-----|------|------|
| COMPLETED → PROCESSING | 완료 거래 재처리 위험 | ❌ 예외 발생 |
| FAILED → COMPLETED | 실패 거래 강제 성공 | ❌ 예외 발생 |
| SETTLED → CANCELLED | 정산 후 취소는 별도 이벤트 필요 | ❌ 예외 발생 |
| RECEIVED → COMPLETED | 검증 단계 생략 | ❌ 예외 발생 |
| CANCELLED → COMPLETED | 취소된 거래 복구 불가 | ❌ 예외 발생 |

**검증 방법**:
```python
def test_invalid_state_transitions_are_blocked():
    event = TransactionEvent(status="COMPLETED")
    
    # 금지된 전이 시도
    with pytest.raises(InvalidStateTransitionError):
        event.change_status("PROCESSING")
    
    with pytest.raises(InvalidStateTransitionError):
        event.change_status("VALIDATED")

def test_valid_transitions_succeed():
    event = TransactionEvent(status="RECEIVED")
    
    event.change_status("VALIDATED")
    assert event.status == "VALIDATED"
    
    event.change_status("PROCESSING")
    assert event.status == "PROCESSING"
    
    event.change_status("COMPLETED")
    assert event.status == "COMPLETED"
```

---

### 규칙 6️⃣ Redis 장애가 발생해도 최종 정합성은 보장된다

**명칭**: Redis Failure Resilience (RFR)

**정의**:
```
Redis Down 상황에서도
PostgreSQL의 Unique Constraint와 Transaction으로
중복 거래 반영이 막혀야 한다.
```

**예시**:
```
상황:
- Redis 서버 다운
- 동일 이벤트 100번 요청

예상 결과:
- transaction_event: 1건
- ledger_entry: 1건
- account.balance: 1회 변경
- API 응답: 성공 또는 재시도 권장
```

**구현**:
```python
def process_event(command):
    # Redis Lock 시도 (실패해도 계속 진행)
    lock_acquired = redis_client.acquire_lock(
        key=f"lock:{command.idempotency_key}",
        ttl=10
    )
    
    if not lock_acquired:
        log.warning("Redis lock failed, proceeding with DB fallback")
    
    # PostgreSQL Transaction (필수)
    with db.transaction():
        idem = idempotency_repository.find_for_update(
            command.idempotency_key
        )
        
        if idem and idem.is_completed():
            # Redis Cache Miss 상황에서도 DB에서 복구
            return idem.response_body
        
        # Unique Constraint로 중복 방지
        event = transaction_event_repository.insert(command)
        ledger = ledger_service.create_entry(...)
        
        db.commit()
    
    return response
```

**검증 방법**:
```bash
# Redis 종료
docker stop redis

# 동일 이벤트 100번 요청 (k6 또는 Postman)
k6 run tests/k6/duplicate-storm.js

# 검증
SELECT COUNT(*) FROM transaction_events WHERE external_event_id = 'TEST-001'
# 결과: 1 ✅
```

---

## 정합성 검증 체크리스트

### 코드 리뷰 체크리스트

- [ ] `external_event_id` UNIQUE Constraint 있는가?
- [ ] `idempotency_key` UNIQUE Constraint 있는가?
- [ ] `ledger_entry.transaction_event_id` UNIQUE 있는가?
- [ ] 상태 전이 검증 로직이 있는가?
- [ ] Redis Down 시 DB fallback이 있는가?
- [ ] Request Hash 검증이 있는가?

### 테스트 체크리스트

- [ ] 동일 이벤트 100번 동시 요청 테스트 (중복 방지)
- [ ] 동일 Idempotency Key 재요청 테스트 (응답 일관성)
- [ ] Idempotency Key + 다른 Body 테스트 (409 Conflict)
- [ ] 금지된 상태 전이 테스트 (예외 발생)
- [ ] Redis Down 시나리오 테스트 (DB Fallback)
- [ ] Ledger 기반 잔액 일관성 테스트

### 배포 전 체크리스트

- [ ] 모든 정합성 테스트 통과
- [ ] k6 부하 테스트 중복 거래 0건
- [ ] 모니터링 대시보드 준비
- [ ] 장애 롤백 계획 수립

---

## 문서 내용 정리

- **문제 정의** → [docs/01-problem-definition.md](01-problem-definition.md)
- **도메인 범위** → [docs/02-domain-scope.md](02-domain-scope.md)
- **정합성 규칙** ✅ 현재 문서
- **개발 로드맵** → [docs/04-development-roadmap.md](04-development-roadmap.md)
