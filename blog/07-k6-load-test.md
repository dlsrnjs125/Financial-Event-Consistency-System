# 7편. k6로 중복 이벤트 폭주 상황 재현하기

## 들어가며

테스트를 통과했지만 실제 트래픽에서도 정합성이 유지되는지 검증해야 합니다.

이 편에서는 **k6 부하 테스트**로 중복 이벤트 폭주 상황을 재현합니다.

---

## k6 시나리오

### Smoke Test (배포 직후)
```javascript
export const options = {
  vus: 5,
  duration: '10s'
};

export default function() {
  const res = http.post(
    `${BASE_URL}/api/v1/transaction-events`,
    JSON.stringify({
      external_event_id: `BANK-${Date.now()}`,
      account_id: 'ACC-001',
      event_type: 'DEPOSIT',
      amount: 10000
    }),
    {
      headers: { 'Idempotency-Key': `idem-${Date.now()}` }
    }
  );
  
  check(res, {
    'status 200': (r) => r.status === 200,
    'response time < 100ms': (r) => r.timings.duration < 100
  });
}
```

### Peak Load (중복 폭주)
```javascript
export const options = {
  vus: 100,
  duration: '60s',
  thresholds: {
    'http_req_duration': ['p95<500', 'p99<1000'],
    'http_req_failed': ['rate<0.01']
  }
};

export default function() {
  const idempotencyKey = `idem-duplicate-test`;
  
  // 모든 VU가 같은 Idempotency Key로 요청
  const res = http.post(
    `${BASE_URL}/api/v1/transaction-events`,
    JSON.stringify({
      external_event_id: `BANK-DUPLICATE-001`,
      account_id: 'ACC-001',
      event_type: 'DEPOSIT',
      amount: 10000
    }),
    {
      headers: { 'Idempotency-Key': idempotencyKey }
    }
  );
  
  check(res, {
    'status 200': (r) => r.status === 200 || r.status === 409,
    'no 500 errors': (r) => r.status !== 500
  });
}
```

---

## 검증 지표

### 성능 지표
```
p50: 50ms 이하
p95: 300ms 이하
p99: 1000ms 이하
error_rate: 1% 이하
```

### 정합성 지표
```
duplicate_processed_count: 0
invalid_state_transition_count: 0
ledger_entries_for_event: 1
balance_increment: 1회만
```

### 시나리오별 결과 기록표

| Scenario | VUs | p50 | p95 | p99 | error rate | duplicate rate |
|----------|-----|-----|-----|-----|------------|----------------|
| smoke | 10 | TBD | TBD | TBD | TBD | 0% |
| normal | 50 | TBD | TBD | TBD | TBD | 0% |
| peak | 300 | TBD | TBD | TBD | TBD | 0% |
| duplicate storm | 100 | TBD | TBD | TBD | TBD | 0% |

---

## DB 검증

```python
def verify_consistency_after_load_test():
    """부하 테스트 후 정합성 확인"""
    
    # 1. external_event_id 중복 확인
    duplicates = db.query(
        func.count(TransactionEvent.external_event_id)
    ).group_by(
        TransactionEvent.external_event_id
    ).having(
        func.count(TransactionEvent.external_event_id) > 1
    ).all()
    
    assert len(duplicates) == 0, "External event ID 중복 발견"
    
    # 2. Ledger Entry 1:1 매핑 확인
    duplicate_ledgers = db.query(
        func.count(LedgerEntry.transaction_event_id)
    ).group_by(
        LedgerEntry.transaction_event_id
    ).having(
        func.count(LedgerEntry.transaction_event_id) > 1
    ).all()
    
    assert len(duplicate_ledgers) == 0, "Ledger Entry 중복 발견"
    
    # 3. Balance 계산 검증
    account = db.query(Account).filter_by(id='ACC-001').first()
    total_ledger = db.query(
        func.sum(LedgerEntry.amount)
    ).filter_by(account_id='ACC-001').scalar()
    
    assert account.balance == total_ledger, "Balance 불일치"
```

---

## 다음 편에서

8편에서는 Prometheus/Grafana로 모니터링 대시보드를 구성합니다.
