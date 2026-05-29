# 6편. 잘못된 상태 전이를 막는 테스트 전략

## 들어가며

상태 머신을 정의했지만, 그것만으로는 부족합니다.

**테스트로 고정해야 합니다.**

이 편에서는 상태 전이 테스트, CI Gate, 배포 차단을 다룹니다.

---

## 테스트 계층

### Unit Test: 상태 머신 테스트

```python
class TestStateMachine:
    def test_normal_transition_path(self):
        sm = TransactionStateMachine(TransactionStatus.RECEIVED)
        sm.transition_to(TransactionStatus.VALIDATED)
        sm.transition_to(TransactionStatus.PROCESSING)
        sm.transition_to(TransactionStatus.COMPLETED)
        assert sm.current_status == TransactionStatus.COMPLETED
    
    def test_completed_cannot_go_back_to_processing(self):
        sm = TransactionStateMachine(TransactionStatus.COMPLETED)
        with pytest.raises(InvalidStateTransition):
            sm.transition_to(TransactionStatus.PROCESSING)
    
    def test_failed_cannot_become_completed(self):
        sm = TransactionStateMachine(TransactionStatus.FAILED)
        with pytest.raises(InvalidStateTransition):
            sm.transition_to(TransactionStatus.COMPLETED)
```

### Integration Test: API + DB

```python
class TestTransactionEventAPI:
    def test_event_status_transition_persisted_to_db(self):
        resp = client.post(
            "/api/v1/transaction-events",
            json={
                "external_event_id": "BANK-005",
                "account_id": "ACC-001",
                "event_type": "DEPOSIT",
                "amount": 10000
            },
            headers={"Idempotency-Key": "idem-005"}
        )
        
        event_id = resp.json()["event_id"]
        
        # DB에서 확인
        event = db.query(TransactionEvent).filter_by(id=event_id).first()
        assert event.status == "COMPLETED"
```

### Consistency Test: 제약조건 검증

```python
class TestConsistency:
    def test_duplicate_external_event_id_raises_error(self):
        """같은 external_event_id는 중복 생성 불가"""
        req = {
            "external_event_id": "BANK-006",
            "account_id": "ACC-001",
            "event_type": "DEPOSIT",
            "amount": 5000
        }
        
        resp1 = client.post(
            "/api/v1/transaction-events",
            json=req,
            headers={"Idempotency-Key": "idem-006"}
        )
        assert resp1.status_code == 200
        
        # 다른 Idempotency Key, 같은 external_event_id
        resp2 = client.post(
            "/api/v1/transaction-events",
            json=req,
            headers={"Idempotency-Key": "idem-007"}
        )
        
        # external_event_id UNIQUE constraint 위반
        assert resp2.status_code == 409 or db.count(ledger_entries) == 1
```

---

## CI/CD Gate

### GitHub Actions Workflow

```yaml
name: Consistency Test Gate

on: [pull_request]

jobs:
  consistency-test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: password
      redis:
        image: redis:7
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Run State Machine Tests
        run: pytest tests/unit/test_state_machine.py -v
      
      - name: Run Consistency Tests
        run: pytest tests/consistency/test_duplicate_prevention.py -v
      
      - name: Run Integration Tests
        run: pytest tests/integration/test_transaction_api.py -v
      
      - name: Check Duplicate Prevention
        run: pytest tests/consistency/test_100_concurrent_requests.py -v
```

### 배포 차단 기준
```
❌ Unit Test 실패
❌ Consistency Test 실패
❌ 중복 이벤트 처리 감지
❌ 잘못된 상태 전이 허용 코드 발견
✅ 모든 테스트 통과 → 배포 진행
```

---

## 테스트 목록

| 테스트 | 검증 내용 | Gate |
|-------|---------|------|
| test_received_to_validated | 정상 전이 | - |
| test_completed_cannot_go_back | 잘못된 전이 차단 | ✅ 필수 |
| test_failed_cannot_become_completed | 실패 상태 고정 | ✅ 필수 |
| test_100_concurrent_same_event | 중복 처리 방지 | ✅ 필수 |
| test_redis_down_prevents_duplicate | Redis 장애 | ✅ 필수 |
| test_idempotency_key_conflict | 다른 Body 거부 | ✅ 필수 |

---

## 배포 전 체크리스트

- [ ] 모든 상태 머신 테스트 통과
- [ ] 중복 요청 테스트 통과
- [ ] Redis 없이도 중복 방지 확인
- [ ] DB Migration 성공
- [ ] OpenAPI 스키마 검증 통과

---


## 테스트를 설계 문서처럼 사용한 이유

상태 전이는 문서로만 관리하면 코드와 쉽게 어긋난다. 그래서 상태 전이표에 있는 허용/금지 케이스를 unit test로 옮겼다.

정상 경로만 테스트하면 부족했다. 실제 장애는 대부분 금지 전이에서 드러난다.

```text
COMPLETED -> PROCESSING
FAILED -> COMPLETED
SETTLED -> CANCELLED
```

이런 전이는 정상 UI나 정상 API 흐름에서는 잘 발생하지 않는다. 하지만 retry, duplicate event, cancel event, 복구 worker가 섞이면 실수로 호출될 수 있다.

그래서 테스트 기준을 다음처럼 나눴다.

- domain unit test: 상태 머신 순수 규칙 검증
- service unit test: idempotency decision과 상태 변경 흐름 검증
- integration test: API 응답과 DB 상태가 함께 맞는지 검증
- consistency test: 중복 요청 후 Ledger와 event row가 중복되지 않는지 검증

CI Gate에 상태 전이 테스트를 넣은 이유도 여기에 있다. 잘못된 상태 전이를 허용하는 코드는 배포 전에 실패해야 한다. 운영에서 invalid transition이 발생하면 `financial_invalid_state_transition_total` metric과 구조화 로그로 추적할 수 있게 했다.

남은 한계는 분산 복구 worker다. 여러 worker가 같은 FAILED 이벤트를 동시에 claim하면 단순 상태 머신만으로는 부족하고, PostgreSQL의 조건부 update나 `FOR UPDATE SKIP LOCKED` 같은 claim 전략이 필요하다.
