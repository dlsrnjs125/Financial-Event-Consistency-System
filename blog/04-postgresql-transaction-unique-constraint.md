# 4편. PostgreSQL Transaction과 Unique Constraint로 정합성 보장하기

## 들어가며

Idempotency Key와 상태 머신만으로도 불완전합니다.

왜냐하면 **Redis 장애가 발생할 수 있기 때문**입니다.

따라서 PostgreSQL의 **ACID Transaction과 Unique Constraint를 최종 방어선**으로 삼아야 합니다.

---

## PostgreSQL Transaction 처리 흐름

### 정상 처리 흐름
```
1️⃣ BEGIN TRANSACTION
2️⃣ Idempotency Key 확인 (FOR UPDATE로 Row Lock)
3️⃣ TransactionEvent INSERT
4️⃣ Account Row Lock 획득 (FOR UPDATE)
5️⃣ 상태 전이 검증
6️⃣ LedgerEntry INSERT (UNIQUE Constraint 있음)
7️⃣ Account balance 업데이트
8️⃣ IdempotencyRecord 상태 업데이트
9️⃣ COMMIT ✅
```

### 중복 요청 시나리오
```
[요청 1] BEGIN → INSERT ledger_entry (성공) → COMMIT
         ↓
[요청 2] BEGIN → INSERT ledger_entry (같은 transaction_event_id)
         → UNIQUE Constraint 위반 ❌
         → Constraint Violation Exception
         → ROLLBACK

결과: LedgerEntry는 1건만 생성됨!
```

---

## 필수 Unique Constraint

### 1. External Event ID (외부 이벤트 중복 방지)
```sql
CREATE UNIQUE INDEX ux_transaction_event_external_event_id
  ON transaction_events(external_event_id);
```

**목적**: 같은 external_event_id로 2개 이상의 거래가 생성되는 것 방지

**시나리오**:
```
BANK-A-20260527-0001이 100번 들어옴
  ↓
transaction_events 테이블
  first insert: 성공
  second insert: UNIQUE constraint violation ❌
  
결과: 1행만 존재
```

### 2. Idempotency Key (멱등성 기록 중복 방지)
```sql
CREATE UNIQUE INDEX ux_idempotency_key
  ON idempotency_records(idempotency_key);
```

### 3. Transaction Event ID → Ledger Entry (1:1 매핑)
```sql
CREATE UNIQUE INDEX ux_ledger_transaction_event_id
  ON ledger_entries(transaction_event_id);
```

**목적**: 하나의 이벤트가 장부에 여러 번 기록되는 것 방지

**중요성**:
```
하나의 DEPOSIT 이벤트 → 정확히 1개의 LedgerEntry
→ 잔액 증가 1회만 보장
```

---

## Transaction 의사 코드

```python
def process_transaction_event(command):
    """
    거래 이벤트 처리 (Transaction 보장)
    
    Args:
        command: TransactionEventCommand
        
    Returns:
        TransactionEventResponse
        
    Raises:
        DuplicateExternalEventError (UNIQUE constraint)
        DuplicateIdempotencyKeyError (UNIQUE constraint)
        InvalidStateTransitionError (상태 전이 검증)
        InsufficientBalanceError (잔액 부족)
    """
    
    with db.transaction():
        # 1. Idempotency Key 확인 (Row Lock)
        idem = idempotency_repo.find_for_update(
            command.idempotency_key
        )
        
        if idem:
            if idem.request_hash != compute_hash(command):
                raise DuplicateIdempotencyKeyError(
                    "Same idempotency key with different body"
                )
            
            if idem.status == 'COMPLETED':
                return idem.response_body
            elif idem.status == 'FAILED':
                raise idem.exception
            else:  # PROCESSING
                return 202  # Accepted
        
        # 2. 멱등성 기록 생성 (PROCESSING 상태)
        idem = idempotency_repo.create(
            idempotency_key=command.idempotency_key,
            request_hash=compute_hash(command),
            status='PROCESSING'
        )
        
        try:
            # 3. TransactionEvent 생성 (UNIQUE constraint 적용)
            event = transaction_event_repo.insert(
                external_event_id=command.external_event_id,
                account_id=command.account_id,
                event_type=command.event_type,
                amount=command.amount,
                occurred_at=command.occurred_at
            )
            # 만약 같은 external_event_id가 이미 있으면
            # → UNIQUE constraint violation
            # → Exception 발생 → ROLLBACK
            
            # 4. Account Row Lock 획득
            account = account_repo.find_for_update(
                command.account_id
            )
            
            # 5. 상태 전이 검증
            event.validate_transition("VALIDATED")
            event.change_status("VALIDATED")
            
            event.validate_transition("PROCESSING")
            event.change_status("PROCESSING")
            
            # 6. 사업 로직 검증 (예: 잔액 충분한가)
            if command.event_type == "WITHDRAW":
                if account.balance < command.amount:
                    raise InsufficientBalanceError()
            
            # 7. LedgerEntry 생성 (UNIQUE constraint 적용)
            ledger = ledger_repo.insert(
                transaction_event_id=event.id,
                account_id=account.id,
                event_type=command.event_type,
                amount=command.amount if command.event_type == "DEPOSIT" else -command.amount,
                balance_after=account.balance + (
                    command.amount if command.event_type == "DEPOSIT" else -command.amount
                )
            )
            # 같은 transaction_event_id로 2개 이상의 ledger_entry 생성 시
            # → UNIQUE constraint violation
            # → Exception 발생 → ROLLBACK
            
            # 8. Account balance 갱신
            new_balance = account.balance + (
                command.amount if command.event_type == "DEPOSIT" else -command.amount
            )
            account_repo.update_balance(account.id, new_balance)
            
            # 9. 상태 전이 완료
            event.validate_transition("COMPLETED")
            event.change_status("COMPLETED")
            
            # 10. 상태 이력 저장
            event_history_repo.create(
                transaction_event_id=event.id,
                old_status="PROCESSING",
                new_status="COMPLETED",
                reason="Transaction completed"
            )
            
            # 11. 멱등성 기록 업데이트
            response = TransactionEventResponse(
                event_id=event.id,
                external_event_id=event.external_event_id,
                status="COMPLETED",
                balance_after=new_balance,
                processed=True,
                duplicated=False
            )
            
            idempotency_repo.mark_completed(
                idem.id,
                response_body=response.to_dict()
            )
            
            # 12. COMMIT (모든 변경사항 저장)
            return response
            
        except TransactionProcessingError as exc:
            # 모든 변경사항 ROLLBACK
            idempotency_repo.mark_failed(
                idem.id,
                error_message=exc.safe_message
            )
            raise
```

---

## Row Lock (FOR UPDATE) 사용

### 왜 필요한가?
```
동시 요청 2개가 동시에 같은 Account를 조회
  ↓
둘 다 balance = 100,000 조회
  ↓
req1: balance = 100,000 - 10,000 = 90,000 UPDATE
req2: balance = 100,000 - 20,000 = 80,000 UPDATE
  ↓
결과: balance = 80,000 (잘못됨! 실제로는 70,000이어야 함)
```

### FOR UPDATE로 해결
```sql
-- Account Row Lock 획득
SELECT * FROM accounts 
WHERE id = $1 
FOR UPDATE;

-- 락을 획득한 트랜잭션만 읽고 쓸 수 있음
-- 다른 트랜잭션은 이 행이 해제될 때까지 대기
```

---

## 테스트

### 테스트 1: 동일 이벤트 100번 동시 요청
```python
def test_same_external_event_only_creates_one_ledger_entry():
    account = create_account()
    
    def make_request():
        return client.post(
            "/api/v1/transaction-events",
            json={
                "external_event_id": "BANK-001",
                "account_id": account.id,
                "event_type": "DEPOSIT",
                "amount": 10000
            },
            headers={"Idempotency-Key": "idem-001"}
        )
    
    # 100개의 동시 요청
    responses = concurrent.run(make_request, times=100)
    
    # 검증
    assert all(r.status_code in [200, 409] for r in responses)
    assert db.count(transaction_events) == 1  # ✅ 1개만
    assert db.count(ledger_entries) == 1      # ✅ 1개만
    assert account.balance == 10000            # ✅ 1회만 증가
```

### 테스트 2: Redis 없이도 중복 방지
```python
def test_duplicate_prevention_without_redis():
    redis.shutdown()  # Redis 끔
    
    account = create_account()
    
    # 같은 이벤트를 100번 요청 (Redis 없음)
    responses = concurrent.run(
        lambda: client.post(
            "/api/v1/transaction-events",
            json={
                "external_event_id": "BANK-002",
                "account_id": account.id,
                "event_type": "DEPOSIT",
                "amount": 5000
            },
            headers={"Idempotency-Key": "idem-002"}
        ),
        times=100
    )
    
    # 검증: PostgreSQL만으로도 정합성 보장됨
    assert db.count(ledger_entries) == 1  # ✅
    assert account.balance == 5000        # ✅
```

---

## 핵심 메시지

> **Redis Lock은 동시 요청을 줄이는 역할이고, PostgreSQL Unique Constraint와 Transaction은 중복 반영을 최종적으로 차단하는 역할이다.**
> 
> **따라서 Redis 장애가 발생해도 정합성은 깨지지 않는다.**

---


## 개발 중 마주친 동시성 문제

PostgreSQL unique constraint를 두면 중복 insert는 막을 수 있다. 하지만 여기서 끝이 아니다. 동시 요청이 들어오면 한 요청은 성공하고 다른 요청은 unique conflict를 만난다. 이때 conflict를 그대로 500으로 올리면 사용자는 서버 장애로 보게 된다.

그래서 conflict 처리 방식을 바꿨다.

1. DB transaction 안에서 이벤트와 Ledger를 생성한다.
2. unique conflict가 발생하면 transaction을 rollback한다.
3. 같은 `external_event_id` 또는 idempotency record를 한 번 다시 읽는다.
4. 이미 처리된 결과가 있으면 duplicate/replay 응답으로 돌려준다.
5. 실제 DB 장애라면 5xx/503으로 구분한다.

이 흐름은 Redis 장애와도 연결된다. Redis lock이 있으면 DB까지 들어오는 중복 요청을 줄일 수 있지만, Redis가 죽으면 중복 요청이 DB까지 도달한다. 이때 최종 방어선은 PostgreSQL unique constraint여야 한다.

검증은 Redis를 끄고 duplicate storm을 실행한 뒤 SQL로 확인했다.

```bash
make failure-redis-down
make k6-redis-down-duplicate-storm
make k6-verify
```

Phase 9에서는 Redis Down 중 ledger 중복은 0건이었지만 일부 5xx가 발생했다. 그래서 Phase 10에서 unique conflict 후 read/retry 경로를 보강했다. 이 수정의 핵심은 "중복을 막는 것"과 "중복 요청에 안정적인 응답을 주는 것"을 분리해 본 점이다.

남은 한계는 lock wait과 connection pool이다. unique constraint는 정합성을 지키지만, 동시성이 커지면 latency와 pool 사용량이 증가한다. 이 부분은 PostgreSQL exporter나 SQLAlchemy pool metric이 보강되면 더 정확히 볼 수 있다.
