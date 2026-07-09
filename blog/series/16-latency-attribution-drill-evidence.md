# k6 p99가 튀었을 때 바로 DB 탓을 하면 안 되는 이유

k6 p95/p99는 사용자가 느낀 증상을 보여준다. 하지만 증상은 원인 확정이 아니다. 같은 p99 상승도 Nginx edge, FastAPI handler, Redis, PostgreSQL, outbound dependency, client network path 중 어디서든 생길 수 있다.

이 글은 latency attribution analyzer와 drill evidence runner를 묶어, 성능 장애를 계층별 원인 후보로 좁힌 과정을 정리한다.

## p99 상승을 계층별 evidence로 나눴다

예를 들어 이런 경우는 application 내부보다 edge/client path를 먼저 의심한다.

```text
k6 p99 high
nginx request_time high
nginx upstream_time normal
fastapi handler normal
=> edge/client network latency candidate
```

반대로 DB 후보는 이런 형태에 가깝다.

```text
k6 p99 high
nginx upstream_time high
fastapi handler high
postgres phase dominant
=> PostgreSQL pool/lock/latency candidate
```

## latency classification 예시

LAT drill은 숫자 하나가 아니라 evidence 조합을 만든다.

| Case | k6 | Nginx | FastAPI | PostgreSQL | Redis | 판단 |
| --- | --- | --- | --- | --- | --- | --- |
| LAT-001 | p99 high | request_time high, upstream normal | normal | normal | normal | edge/client path |
| LAT-002 | p99 high | upstream high | handler high | phase dominant | normal | DB 후보 |
| LAT-003 | p99 high | upstream high | handler high | normal | fallback 증가 | Redis fallback 후보 |
| LAT-004 | p99 high | normal | outbound wait high | normal | normal | external dependency 후보 |
| LAT-005 | p99 normal | normal | normal | normal | normal | latency anomaly 아님 |
| LAT-006 | p99 high | mixed | mixed | mixed | mixed | insufficient evidence |

이 표의 목적은 root cause를 단정하는 것이 아니라, 어떤 계층을 다음으로 조사해야 하는지 좁히는 것이다.

## attribution은 root cause 확정이 아니라 조사 순서 정리다

latency attribution 결과가 `DB 후보`라고 해서 DB가 원인이라고 단정할 수는 없다. 이 결과는 운영자가 다음에 무엇을 봐야 하는지 우선순위를 정하는 데 사용한다.

예를 들어 PostgreSQL 후보로 분류되면 다음 단계에서는 실제 DB lock view, slow query log, connection pool usage, transaction wait, index usage를 확인해야 한다. Redis fallback 후보라면 fallback count, timeout, cache miss, Redis network latency를 봐야 한다.

이번 프로젝트의 analyzer는 local sample evidence를 기준으로 candidate를 분류한다. root cause 확정은 더 많은 telemetry와 운영 context가 필요하다.

## latency drill은 숫자가 아니라 evidence를 만든다

LAT-001~LAT-006 시나리오는 안전한 evidence runner로 묶었다. 기본 demo는 DB lock holder, Redis down, network delay 같은 destructive action을 실행하지 않는다.

대신 attribution analyzer가 읽을 수 있는 input evidence를 만들고 expected classification과 actual classification을 비교한다.

## synthetic drill과 실제 장애는 다르다

LAT-001~LAT-006은 안전한 sample evidence를 만들기 위한 drill이다. 실제 운영 장애처럼 DB lock holder를 오래 잡거나, network delay를 주입하거나, Redis를 강제로 내리는 destructive action을 기본 demo에 넣지 않았다.

이 선택은 안전하지만 한계도 있다. 실제 장애의 복잡한 상호작용은 완전히 재현하지 못한다. 대신 기본 demo는 analyzer 계약과 evidence schema가 깨지지 않는지 확인하는 회귀 검증으로 사용한다.

```bash
make ph10-latency-attribution-demo
make ph11-latency-drill-demo
```

## 트러블슈팅: 저장된 actual 값만 믿으면 validator가 속을 수 있다

처음에는 report에 저장된 expected/actual 값만 비교하면 충분해 보였다. 하지만 누군가 둘 다 같은 잘못된 값으로 바꾸면 validator가 속을 수 있다.

그래서 validator는 `ph10_input_scenario`로 evidence를 다시 만들고 attribution analyzer를 재실행한다.

```text
stored actual classification
  vs
recomputed classification from attribution analyzer
```

둘이 다르면 report가 조작됐거나 analyzer 계약이 깨진 것으로 본다.

## consistency counter를 같이 본 이유

latency drill 중 duplicate ledger나 reconciliation failure가 나오면 performance warning이 아니라 consistency incident candidate다.

그래서 drill evidence에는 latency 숫자와 consistency counter를 함께 둔다.

```text
p99 high
duplicate ledger 0
=> latency candidate

p99 normal
duplicate ledger > 0
=> consistency incident candidate
```

성능 장애와 정합성 장애는 함께 관찰하지만, 대응 우선순위는 다르다.

latency와 5xx에는 error budget을 둘 수 있지만, duplicate ledger나 account balance mismatch는 error budget을 두지 않는다. 1건이라도 발생하면 성능 경고가 아니라 정합성 incident 후보로 올린다.

## trace_id는 metric label이 아니라 log correlation key다

`trace_id`, `request_id`, `event_id`, retry key는 단일 요청을 추적할 때 필요하다.

하지만 Prometheus metric label로 넣으면 안 된다. 요청마다 label 값이 달라져 cardinality가 폭증하고, 민감 identifier가 metric storage로 흘러갈 위험도 커진다.

그래서 high-cardinality identifier는 log correlation key로 남기고, metric label은 route, status class, dependency, classification처럼 집계 가능한 값으로 제한했다.

## 남은 한계

이 글의 drill은 local sample evidence 기반의 attribution drill이다. 실제 운영 root cause 확정에는 tracing, DB lock view, exporter metric, network telemetry, external dependency SLA가 더 필요하다.

결론은 간단하다. k6 p99는 출발점이고, root cause는 계층별 evidence와 consistency boundary를 함께 봐야 좁힐 수 있다.
