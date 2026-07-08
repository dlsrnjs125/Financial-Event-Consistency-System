# p99가 느려져도 원장이 두 번 반영되면 안 된다

k6 부하 테스트에서 p95, p99, RPS는 중요하다. 하지만 금융 이벤트 시스템에서는 latency보다 먼저 봐야 하는 값이 있다. duplicate ledger count다.

## duplicate storm에서 본 것

중복 요청 폭주 테스트는 같은 이벤트를 반복 전송한다. 이때 API가 일부 느려질 수 있고, Redis fallback 상황에서는 error rate도 올라갈 수 있다.

하지만 이 실험의 핵심 질문은 다르다.

```text
같은 external_event_id가 100번 들어와도
transaction_event는 1건인가?
ledger_entry는 1건인가?
account balance는 1회만 바뀌었는가?
```

## Redis down 결과를 같은 실패로 보지 않았다

Redis down 시나리오에서는 p99가 크게 튈 수 있다. availability는 나빠질 수 있다. 하지만 Redis 없이도 ledger 중복이 0건이면 정합성 방어선은 살아 있다.

성능 저하는 장애 영향이고, 중복 원장 발생은 정합성 사고다. 두 지표를 같은 실패로 보면 운영 판단이 흐려진다.

## evidence로 남긴 기준

`make k6-duplicate`와 `make k6-verify`를 분리했다. 부하를 만든 뒤 PostgreSQL에서 중복 이벤트와 중복 ledger를 확인한다.

이 프로젝트에서 k6는 "성능 숫자를 예쁘게 보이기 위한 도구"가 아니라 "재시도와 중복 폭주 속에서도 원장이 한 번만 반영되는지 확인하는 도구"다.
