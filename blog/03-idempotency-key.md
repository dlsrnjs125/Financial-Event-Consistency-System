# 3편. Idempotency Key로 중복 요청을 방어하는 방법

## 들어가며

상태 머신만으로는 부족합니다.

**같은 Idempotency Key로 다른 금액의 요청**이 오면 어떻게 해야 할까요?

단순히 "기존 결과를 반환"하면 안 됩니다.

---

## Idempotency Key란?

같은 요청이 여러 번 들어와도 결과가 한 번만 반영되도록 요청을 식별하는 키입니다.

### 요청 예시
```http
POST /api/v1/transaction-events
Content-Type: application/json
Idempotency-Key: idem-20260527-001

{
  "external_event_id": "BANK-A-20260527-0001",
  "account_no": "1234567890",
  "event_type": "DEPOSIT",
  "amount": 10000,
  "currency": "KRW",
  "occurred_at": "2026-05-27T10:00:00+09:00"
}
```

---

## 처리 정책

### 상황 1: 새로운 Idempotency Key
```
요청 1: Idempotency-Key: idem-001, {amount: 10000}
  → 신규 처리
  → 응답: {event_id: evt-001, status: COMPLETED, balance_after: 110000}
```

### 상황 2: 같은 Key + 같은 요청 Body
```
요청 1: Idempotency-Key: idem-001, {amount: 10000}
  → 처리 완료, 응답 저장됨
  ↓
요청 2: Idempotency-Key: idem-001, {amount: 10000} (재전송)
  → 기존 결과 반환
  → 응답: {event_id: evt-001, status: COMPLETED, balance_after: 110000}
```

### 상황 3: 같은 Key + 다른 요청 Body ❌ CONFLICT
```
요청 1: Idempotency-Key: idem-001, {amount: 10000}
  → 처리 완료
  ↓
요청 2: Idempotency-Key: idem-001, {amount: 50000} (다른 금액!)
  → 409 Conflict 반환
  → 메시지: "Same idempotency key with different request body"
  ↓
결과: 첫 번째 요청의 {amount: 10000}만 반영됨
```

### 상황 4: 처리 중 같은 Key 재요청
```
요청 1: Idempotency-Key: idem-001, {amount: 10000}
  → 처리 중... (DB 트랜잭션 진행 중)
  ↓
요청 2: Idempotency-Key: idem-001, {amount: 10000} (재전송)
  → 202 Accepted 반환 또는 처리 상태 반환
  → 메시지: "Already processing, check later"
  ↓
요청 1 완료 후
  ↓
요청 2: 재조회 시 최종 결과 반환
```

---

## 요청 Hash 저장이 필요한 이유

같은 Idempotency Key라도 Body가 다르면 위험합니다.

```python
# 악의적 또는 실수로 발생하는 상황
요청 1: Idempotency-Key: idem-001
{
  "amount": 10000
}
← 이 요청이 처리되어 잔액 +10000

요청 2: Idempotency-Key: idem-001
{
  "amount": 50000  ← 다른 금액!
}
← 단순히 "중복"이라고 무시하면 안 됨
← 409 Conflict를 반환하고 첫 번째 금액만 반영되어야 함
```

### Hash 저장 방식
```python
import hashlib
import json

def compute_request_hash(request_body: dict) -> str:
    """
    요청 Body를 정규화하고 SHA256 해시 생성
    """
    # 1. JSON 문자열로 변환 (소수점 정규화 등)
    normalized = json.dumps(request_body, sort_keys=True, separators=(',', ':'))
    
    # 2. SHA256 해시 계산
    return hashlib.sha256(normalized.encode()).hexdigest()

# 예시
req1 = {"amount": 10000, "account_id": "ACC-001"}
hash1 = compute_request_hash(req1)
# hash1 = "a1b2c3d4e5f6..."

req2 = {"amount": 50000, "account_id": "ACC-001"}
hash2 = compute_request_hash(req2)
# hash2 = "x9y8z7w6v5u4..." (다름!)
```

---

## 멱등성 기록 저장 전략

### IdempotencyRecord 테이블
```sql
CREATE TABLE idempotency_records (
  id BIGSERIAL PRIMARY KEY,
  idempotency_key VARCHAR(255) UNIQUE NOT NULL,
  request_hash VARCHAR(64) NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'PROCESSING',
  response_body JSONB,
  error_message TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP
);

CREATE INDEX idx_idempotency_key ON idempotency_records(idempotency_key);
```

### 처리 흐름 (의사 코드)
```python
def handle_event(idempotency_key, request_body):
    # 1. 요청 Hash 계산
    request_hash = compute_request_hash(request_body)
    
    # 2. 멱등성 기록 조회 (FOR UPDATE로 Row Lock)
    existing = db.select_for_update(
        idempotency_records,
        where=idempotency_key == idempotency_key
    )
    
    if existing:
        # 기존 요청 발견
        if existing.request_hash != request_hash:
            # Hash 불일치 = 다른 요청
            return 409 Conflict
        
        if existing.status == 'PROCESSING':
            return 202 Accepted  # 처리 중
        elif existing.status == 'COMPLETED':
            return 200 OK with existing.response_body
        else:  # FAILED
            return existing.error
    
    # 3. 새로운 요청 → 멱등성 기록 생성 (PROCESSING 상태)
    idem_record = db.insert(
        idempotency_records,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        status='PROCESSING'
    )
    
    try:
        # 4. 실제 처리 (Transaction 시작)
        response = process_transaction(request_body)
        
        # 5. 멱등성 기록 업데이트 (COMPLETED)
        db.update(
            idempotency_records,
            where=id == idem_record.id,
            status='COMPLETED',
            response_body=response,
            completed_at=now()
        )
        
        return 200 OK with response
        
    except Exception as e:
        # 6. 실패 시 FAILED 상태로 저장
        db.update(
            idempotency_records,
            where=id == idem_record.id,
            status='FAILED',
            error_message=str(e)
        )
        raise
```

---

## 테스트

### 테스트 1: 동일 요청 재전송 시 같은 결과 반환
```python
def test_same_idempotency_key_returns_same_result():
    req = {"amount": 10000, "account_id": "ACC-001"}
    
    resp1 = client.post(
        "/api/v1/transaction-events",
        json=req,
        headers={"Idempotency-Key": "idem-001"}
    )
    
    resp2 = client.post(
        "/api/v1/transaction-events",
        json=req,
        headers={"Idempotency-Key": "idem-001"}
    )
    
    assert resp1.json()["event_id"] == resp2.json()["event_id"]
    assert resp1.status_code == 200
    assert resp2.status_code == 200
```

### 테스트 2: 다른 Body로 같은 Key 요청 시 409 반환
```python
def test_same_key_different_body_returns_conflict():
    req1 = {"amount": 10000, "account_id": "ACC-001"}
    req2 = {"amount": 50000, "account_id": "ACC-001"}
    
    resp1 = client.post(
        "/api/v1/transaction-events",
        json=req1,
        headers={"Idempotency-Key": "idem-001"}
    )
    
    resp2 = client.post(
        "/api/v1/transaction-events",
        json=req2,
        headers={"Idempotency-Key": "idem-001"}
    )
    
    assert resp1.status_code == 200
    assert resp2.status_code == 409  # Conflict
    assert "different request body" in resp2.json()["error"]
```

---

## 핵심 메시지

> **Idempotency Key는 단순히 중복 요청을 무시하는 기능이 아니라, 같은 키로 다른 요청이 들어오는 위험까지 차단해야 한다.**

---

## 다음 편에서

4편에서는 PostgreSQL Transaction과 Unique Constraint로 정합성을 최종 보장하는 방법을 다룹니다.
