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

## 무엇을 측정했는가

k6 결과는 두 가지로 나눠서 봤다.

첫 번째는 HTTP 관점이다. p50, p95, p99, RPS, 5xx, unexpected response를 본다. 이 값은 사용자가 느끼는 응답 지연과 API 가용성을 보여준다.

두 번째는 DB 정합성 관점이다. 동일 `external_event_id`가 여러 row로 저장됐는지, 하나의 transaction event에 Ledger가 여러 번 붙었는지 확인한다. 이 프로젝트에서는 HTTP latency가 목표를 넘더라도 DB 중복 반영이 0건이면 정합성은 유지된 것으로 본다. 반대로 latency가 좋아도 Ledger 중복이 1건이라도 발생하면 실패다.

실제 로컬 Docker Compose 환경에서 기록한 주요 결과는 다음과 같다.

| Scenario | 조건 | p50 | p95 | p99 | RPS | error rate | ledger 중복 |
|---|---|---:|---:|---:|---:|---:|---:|
| smoke | 1 VU, 3 iterations | 13.93ms | 83.65ms | 99.27ms | 1.89 req/s | 0.00% | 해당 없음 |
| normal load | 20 VU, 25s | 44.68ms | 181.18ms | 261.73ms | 60.77 req/s | 0.00% | 0건 |
| peak load | 50 VU, 25s | 793.88ms | 1369.66ms | 1490ms | 55.11 req/s | 0.00% | 0건 |
| duplicate storm | 50 VU, 15s | 32.17ms | 70.57ms | 96.81ms | - | 0.00% | 0건 |
| Redis Down | 30 VU, 15s | 614.89ms | 722.21ms | 3490ms | 38.21 req/s | 6.86% | 0건 |

---

## 어떻게 재현했는가

부하 테스트는 Makefile 명령으로 고정했다.

```bash
make local-bg
make k6-smoke
make k6-normal
make k6-peak
make k6-duplicate
make k6-verify
```

Redis 장애 중 duplicate storm은 별도 명령으로 실행했다.

```bash
make failure-redis-down
make k6-redis-down-duplicate-storm
make k6-verify
make failure-redis-up
```

`make k6-verify`는 HTTP 결과가 아니라 PostgreSQL 검증 SQL을 실행한다. 동일 `external_event_id` 중복 row, 동일 `transaction_event_id`의 Ledger 중복 row가 있는지 확인한다.

---


## 트러블슈팅 1: p95보다 먼저 중복 반영을 봤다

duplicate storm은 일반 RPS 테스트가 아니다. 같은 key 또는 같은 event가 동시에 몰릴 때 정합성이 깨지는지 보는 실험이다.

Phase 9 로컬 Docker Compose 기준으로 duplicate storm은 50 VU, 15초 동안 실행했다. 이때 p50은 32.17ms, p95는 70.57ms, p99는 96.81ms였고, 200 응답 6891건, 202 응답 1689건이 발생했다. 중요한 점은 error rate가 0%였고, SQL 검증 결과 ledger 중복이 0건이었다는 점이다.

반대로 peak load에서는 p95가 1369.66ms까지 올라갔다. 이 결과만 보면 성능 목표를 만족하지 못한다. 하지만 5xx는 0%였고 중복 반영도 없었다. 그래서 성능 지표를 다음 순서로 해석했다.

1. duplicate ledger/event count가 0건인가
2. 5xx 또는 unexpected response가 증가했는가
3. p95/p99가 목표를 넘는다면 DB transaction, Redis fallback, lock contention 중 무엇 때문인가

Redis Down 실행에서는 p95 722.21ms, p99 3490ms, error rate 6.86%가 나왔지만 ledger 중복은 0건이었다. 이 결과 때문에 Phase 10에서 Redis fallback hardening을 진행했다. 즉 "중복은 막았지만 장애 시 API 가용성은 부족하다"는 결론을 수치로 확인한 셈이다.

## 트러블슈팅 2: 테스트 코드도 검증 대상이었다

테스트 코드 자체도 검증 대상이었다. `amount: overrides.amount || randomAmount()` 패턴은 `amount=0`을 false로 판단해 랜덤 금액으로 바꿔버린다. 그러면 0원 validation 테스트가 실제로는 0원을 보내지 않는 문제가 생긴다. 이 부분은 `overrides.amount ?? randomAmount()` 또는 `overrides.amount !== undefined` 방식으로 고쳤다.

## 남은 한계

로컬 Docker Compose의 latency와 connection pool 특성은 운영 환경과 다르다. 따라서 위 수치는 운영 절대값이 아니라 설계 비교와 회귀 검증 기준으로 해석해야 한다. 장시간 부하, 실제 네트워크 지연, PostgreSQL exporter 기반 connection metric은 별도 환경에서 다시 봐야 한다.
