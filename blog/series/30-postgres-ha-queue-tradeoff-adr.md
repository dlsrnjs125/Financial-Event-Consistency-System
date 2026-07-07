# 30. PostgreSQL HA와 Queue를 바로 붙이지 않고 ADR로 먼저 분리한 이유

PostgreSQL이 Source of Truth인 금융 이벤트 시스템에서 가장 유혹적인 개선은 두 가지다.

첫째, PostgreSQL HA를 붙인다.
둘째, Kafka나 RabbitMQ 같은 durable queue를 앞에 둔다.

둘 다 좋은 선택지가 될 수 있다.
하지만 지금 프로젝트에서 바로 붙이지 않은 이유는 구현 난이도 때문이 아니라, API 응답 의미와 정합성 책임이 같이 바뀌기 때문이다.

## 1. 문제

현재 API는 PostgreSQL commit이 성공한 뒤에 `COMPLETED` 응답을 줄 수 있다.

PostgreSQL write path가 죽으면 신규 금융 write는 `503 + Retry-After`로 fail-closed 한다.
이 선택은 장애 중 성공률을 낮추지만, 처리 여부가 불명확한 성공 응답을 만들지 않는다.

## 2. 처음에 의심한 방식

처음에는 이런 질문이 생긴다.

- Kafka를 앞에 두면 DB 장애 문제가 바로 해결되는가?
- RDS Multi-AZ를 쓰면 애플리케이션 복구 로직이 필요 없어지는가?
- synchronous replication은 금융 시스템에 항상 좋은가?

답은 모두 "상황에 따라 다르다"에 가깝다.
특히 queue-first는 수신 가능성을 높이지만, 원장 반영 완료를 보장하지 않는다.

## 3. 비교한 선택지

PH8에서는 다섯 가지를 비교했다.

| 선택지 | 핵심 |
| --- | --- |
| Direct PostgreSQL transaction + fail-closed | 현재 구조. `COMPLETED` 의미가 가장 명확하다. |
| PostgreSQL primary/standby HA | DB 단일 장애점을 줄이지만 failover 검증이 필요하다. |
| Synchronous replication | RPO를 낮출 수 있지만 commit latency가 증가한다. |
| Managed DB HA | DB 운영 부담은 줄지만 app retry/readiness 책임은 남는다. |
| Durable queue-first architecture | 수신 가용성은 높지만 `ACCEPTED`와 `COMPLETED`를 분리해야 한다. |

## 4. 선택한 결론

현재 프로젝트는 direct PostgreSQL transaction + fail-closed를 유지한다.

이유는 단순하다.
현재 API의 `COMPLETED`는 PostgreSQL commit evidence가 있어야 설명 가능하다.

Queue-first를 도입한다면 API는 이렇게 바뀌어야 한다.

- `ACCEPTED`: queue가 이벤트를 받았다.
- `COMPLETED`: consumer가 PostgreSQL에 원장 반영을 끝냈다.

두 의미를 섞으면 금융 시스템에서는 위험하다.

HA도 마찬가지다.
HA는 장애 window를 줄일 수 있지만, failover 후 stale connection, primary identity, consistency gate, write resume approval은 여전히 필요하다.

## 5. 구현 중 트러블슈팅

### Queue-first가 정합성 문제를 없애지 않는 문제

- 문제: queue를 앞에 두면 DB 장애 중에도 요청을 받을 수 있지만 ledger posting은 나중에 일어난다.
- 원인: queue durability와 PostgreSQL commit durability는 서로 다른 boundary다.
- 해결: queue-first는 별도 V2 contract 후보로 분리했다.
- 검증: validator가 `ACCEPTED`와 `COMPLETED` 분리가 없으면 실패한다.

### HA가 consistency gate를 대체하지 못하는 문제

- 문제: HA가 있으면 failover 후 바로 write resume을 해도 된다고 오해할 수 있다.
- 원인: failover 중 stale connection과 replication lag가 남을 수 있다.
- 해결: HA option에도 consistency gate와 write resume approval을 필수 control로 넣었다.
- 검증: validator가 이 문구가 없으면 실패한다.

### Decision score가 절대 지표처럼 보이는 문제

- 문제: 1~5 score가 실제 성능 benchmark처럼 보일 수 있다.
- 원인: 숫자는 설명용이어도 절대 수치처럼 읽히기 쉽다.
- 해결: score를 deterministic project-fit signal이라고 명시했다.
- 검증: JSON/Markdown report에 benchmark가 아니라는 note를 남겼다.

### README에 상세 ADR을 넣으면 요약성이 떨어지는 문제

- 문제: HA/Queue 비교표를 README에 넣으면 첫 화면이 무거워진다.
- 원인: README와 ADR의 역할이 다르다.
- 해결: README에는 한 문장과 링크만 두고, 상세 판단은 docs/40과 docs/50에 둔다.
- 검증: README에는 score 표를 넣지 않았다.

## 6. 검증

PH8에서는 실제 HA cluster나 queue middleware를 실행하지 않는다.
대신 decision matrix generator와 validator를 추가했다.

```bash
make ph8-ha-queue-decision-demo
make ph8-ha-queue-decision-validate
make ph8-architecture-check
```

report는 아래 위치에 생성된다.

```text
reports/architecture/ph8-ha-queue-tradeoff/sample-ha-queue-decision-report.json
reports/architecture/ph8-ha-queue-tradeoff/sample-ha-queue-decision-report.md
```

## 7. 결론

이번 단계의 핵심은 기술을 많이 붙이는 것이 아니다.

PostgreSQL HA와 durable queue를 도입할 때 API contract, 정합성 책임, 복구 승인 경계가 어디서 바뀌는지 먼저 설명 가능하게 만드는 것이다.

현재는 direct PostgreSQL transaction + fail-closed를 유지한다.
HA는 production availability 후보로, queue-first는 별도 V2 contract 후보로 남긴다.
