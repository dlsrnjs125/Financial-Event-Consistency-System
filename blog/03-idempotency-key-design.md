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
 # 상황: 악의적 또는 실수로 발생하는 다른 Body 요청
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

 # 예시 request hash
req1 = {"amount": 10000, "account_id": "ACC-001"}
hash1 = compute_request_hash(req1)
 # 결과: hash1 = "a1b2c3d4e5f6..."

req2 = {"amount": 50000, "account_id": "ACC-001"}
hash2 = compute_request_hash(req2)
 # 결과: hash2 = "x9y8z7w6v5u4..." (다름!)
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
        
    except TransactionProcessingError as exc:
        # 6. 실패 시 FAILED 상태로 저장
        db.update(
            idempotency_records,
            where=id == idem_record.id,
            status='FAILED',
            error_message=exc.safe_message
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

## Idempotency 처리 방식별 비교

비교 대상:

1. IdempotencyRecord를 DB에서 매번 조회
2. Redis Cache에 완료 응답 저장 후 반환

측정 지표:

- p50/p95/p99 latency
- `financial_idempotency_hit_total`
- DB query count
- cache hit ratio
- duplicate processing rate

해석 기준:

Redis Cache를 사용해 p95 latency와 DB query count가 줄어들더라도, Redis 장애 시 duplicate processing rate는 0%를 유지해야 한다.

---


## 개발 중 바뀐 판단

처음에는 `Idempotency-Key`만 unique로 저장하면 충분하다고 생각할 수 있다. 하지만 같은 key로 다른 body가 들어오는 경우를 생각하면 문제가 생긴다.

예를 들어 첫 요청은 10,000원 입금이고, 두 번째 요청은 같은 key로 50,000원 입금이라면 어떻게 해야 할까? 단순히 key가 같다는 이유로 첫 응답을 replay하면 client는 50,000원 요청이 처리된 것으로 오해할 수 있다. 반대로 두 번째 요청을 새 요청처럼 처리하면 같은 key의 의미가 깨진다.

그래서 idempotency record에는 key뿐 아니라 canonical request hash를 함께 저장했다.

```text
same key + same body      -> 기존 응답 replay
same key + different body -> 409 Conflict
new key                   -> 신규 처리
```

canonical JSON을 사용한 이유도 여기서 나왔다. JSON key 순서가 바뀌었을 뿐 의미가 같은 요청은 같은 hash를 가져야 한다. 반면 amount, account, event type이 바뀌면 다른 hash가 되어야 한다.

Redis cache를 붙인 뒤에도 기준은 바뀌지 않았다. Redis에 완료 응답을 캐싱하더라도 최종 판단은 DB idempotency record다. cache miss는 장애가 아니고, Redis 장애는 fallback 대상이다.

검증은 같은 key/body 재요청, 같은 key/different body, 완료 응답 replay, 실패 응답 replay를 각각 테스트했다. 이 과정에서 idempotency는 단순 중복 방지가 아니라 "client가 timeout 이후 어떤 응답을 다시 받아야 하는가"의 문제라는 점이 명확해졌다.

남은 한계는 retention 정책이다. idempotency record를 얼마나 오래 보관할지는 외부 금융사의 retry 기간, 감사 요구사항, 저장 비용에 따라 달라진다.
