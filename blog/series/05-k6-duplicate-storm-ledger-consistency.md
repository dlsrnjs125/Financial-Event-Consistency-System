# p99가 느려져도 원장이 두 번 반영되면 안 된다

부하 테스트를 할 때 가장 먼저 보이는 숫자는 p95, p99, RPS, error rate다. 하지만 금융 이벤트 시스템에서 더 무서운 실패는 느린 응답보다 중복 반영이다.

이 글의 목표는 "빠른 API"를 증명하는 것이 아니라, 같은 이벤트가 동시에 몰렸을 때 PostgreSQL 기준으로 원장과 이벤트가 한 번만 남는지 확인하는 것이다.

## 부하 테스트에서 정말 보고 싶었던 것은 RPS가 아니었다

외부 금융 시스템은 네트워크 지연이나 timeout이 발생하면 같은 요청을 다시 보낼 수 있다. 이때 API가 한 번은 성공했고, 클라이언트는 응답을 받지 못했고, 같은 `external_event_id`와 `Idempotency-Key`가 다시 들어오는 상황이 생긴다.

단일 요청 테스트에서는 이 문제가 잘 보이지 않는다. 그래서 k6로 다음 상황을 분리해서 재현했다.

- smoke test: 배포 직후 기본 거래 API가 동작하는가
- normal load: 일반 부하에서 latency와 error rate가 안정적인가
- peak load: 높은 동시성에서 API가 얼마나 느려지는가
- duplicate storm: 같은 이벤트가 몰려도 중복 반영이 없는가
- Redis Down: 보조 계층이 죽어도 PostgreSQL 방어선이 유지되는가

## p99만 보면 정합성 실패를 놓칠 수 있다

처음에는 p95/p99가 threshold 안에 들어오면 좋은 결과라고 생각하기 쉽다. 하지만 이 프로젝트에서는 순서를 반대로 잡았다.

1. duplicate external event count가 0인가
2. duplicate ledger count가 0인가
3. 5xx 또는 unexpected response가 증가했는가
4. 그 다음 p95/p99가 어느 계층 때문에 상승했는가

latency가 목표를 넘더라도 duplicate ledger가 0이면 정합성은 유지된 것이다. 반대로 p99가 좋아도 ledger가 두 번 생기면 실패다.

## k6 시나리오

duplicate storm은 모든 VU가 같은 `external_event_id`와 같은 `Idempotency-Key`로 요청하도록 구성했다.

```javascript
export const options = {
  vus: 50,
  duration: "15s",
};

export default function () {
  const res = http.post(
    `${BASE_URL}/api/v1/transaction-events`,
    JSON.stringify({
      external_event_id: "BANK-DUPLICATE-001",
      account_id: "ACC-001",
      event_type: "DEPOSIT",
      amount: 10000,
    }),
    {
      headers: { "Idempotency-Key": "idem-duplicate-test" },
    }
  );

  check(res, {
    "no 500 errors": (r) => r.status !== 500,
    "accepted or replayed": (r) => [200, 202, 409].includes(r.status),
  });
}
```

여기서 중요한 것은 HTTP 응답 하나하나가 아니라, 실행 후 PostgreSQL에 중복 원장이 남지 않는지다.

## Redis Down은 성능 실패였지만 정합성 실패는 아니었다

실제 로컬 Docker Compose 환경에서 기록한 주요 결과는 다음과 같다. 이 수치는 운영 benchmark가 아니라 설계 검증과 회귀 확인을 위한 sample evidence다.

| 시나리오 | 조건 | p50 | p95 | p99 | RPS | error rate | ledger 중복 | 해석 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| smoke | 1 VU, 3 iterations | 13.93ms | 83.65ms | 99.27ms | 1.89 req/s | 0.00% | 해당 없음 | 배포 직후 기본 확인 |
| normal load | 20 VU, 25s | 44.68ms | 181.18ms | 261.73ms | 60.77 req/s | 0.00% | 0건 | 정상 부하 기준 |
| peak load | 50 VU, 25s | 793.88ms | 1369.66ms | 1490ms | 55.11 req/s | 0.00% | 0건 | 성능 개선 필요, 정합성은 유지 |
| duplicate storm | 50 VU, 15s | 32.17ms | 70.57ms | 96.81ms | - | 0.00% | 0건 | 중복 방어 성공 |
| Redis Down | 30 VU, 15s | 614.89ms | 722.21ms | 3490ms | 38.21 req/s | 6.86% | 0건 | 가용성 저하, 정합성 방어선 유지 |

Redis Down에서는 p99가 3490ms까지 튀고 error rate도 6.86%가 나왔다. 이것은 좋은 성능 결과가 아니다. 하지만 ledger 중복은 0건이었다.

그래서 결론을 이렇게 나눴다.

- Redis 장애 중 API 가용성은 개선 대상이다.
- 그러나 PostgreSQL unique constraint와 transaction boundary는 중복 반영을 막았다.
- 성능 문제와 정합성 문제는 같은 표에서 보되, 실패 의미는 분리해야 한다.

## 재현 명령

부하 테스트는 사람이 매번 다른 옵션으로 실행하지 않도록 Makefile 명령으로 고정했다.

```bash
make local-bg
make k6-smoke
make k6-normal
make k6-peak
make k6-duplicate
make k6-verify
```

Redis 장애 중 duplicate storm은 별도 drill로 실행했다.

```bash
make failure-redis-down
make k6-redis-down-duplicate-storm
make k6-verify
make failure-redis-up
```

`make k6-verify`는 HTTP 결과가 아니라 PostgreSQL 검증 SQL을 실행한다. 동일 `external_event_id` 중복 row, 동일 `transaction_event_id`의 ledger 중복 row가 있는지 확인한다.

## 트러블슈팅 1: p95가 나빠도 ledger 중복 0건이면 다른 실패다

peak load에서는 p95가 1369.66ms까지 올라갔다. 숫자만 보면 성능 목표를 만족하지 못한다.

하지만 5xx는 0%였고 ledger 중복도 없었다. 그래서 이 결과를 "성능 개선 필요"로 분류하되 "정합성 실패"로 부르지는 않았다.

반대로 duplicate storm은 p99가 낮아도 핵심은 latency가 아니다. 같은 이벤트가 동시에 몰렸을 때 DB에 한 번만 남았는지가 핵심이다.

## 트러블슈팅 2: 0원 테스트를 깨뜨린 JavaScript falsy 처리

부하 테스트를 작성하면서 테스트 코드 자체의 버그도 발견했다.

처음에는 request body를 만들 때 다음 패턴을 사용했다.

```javascript
amount: overrides.amount || randomAmount()
```

이 코드는 `amount=0`을 false로 판단해 랜덤 금액으로 바꿔버린다. 그러면 0원 validation 테스트를 넣어도 실제로는 0원이 전송되지 않는다.

수정 후에는 nullish coalescing 또는 명시적 undefined 체크를 사용했다.

```javascript
amount: overrides.amount ?? randomAmount()
```

부하 테스트는 시스템만 검증하는 도구가 아니었다. 테스트가 정말 의도한 입력을 보내는지도 검증 대상이었다.

## 남은 한계

로컬 Docker Compose의 latency와 connection pool 특성은 운영 환경과 다르다. 따라서 위 수치는 운영 절대값이 아니라 설계 비교와 회귀 검증 기준으로만 해석해야 한다.

장시간 부하, 실제 네트워크 지연, PostgreSQL exporter 기반 connection metric, Redis exporter 기반 fallback 분석은 후속 관측성 환경에서 다시 확인해야 한다.
