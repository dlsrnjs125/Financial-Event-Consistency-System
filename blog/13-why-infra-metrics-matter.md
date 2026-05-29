# 13편. 금융 거래 시스템에서 애플리케이션 메트릭만으로 부족했던 이유

## 1. 문제를 어떻게 정의했는가

Phase 8에서는 FastAPI 애플리케이션 custom metric을 만들었다. API 요청 수, p95/p99, transaction event 처리 수, Redis fallback count, readiness dependency status는 거래 처리 흐름을 이해하는 데 충분히 유용했다.

하지만 운영자가 실제 장애를 만났을 때 질문은 조금 다르다.

```text
API p99가 느려졌다.
원인이 API 코드인가?
DB connection 고갈인가?
Redis latency인가?
Nginx upstream 지연인가?
서버 CPU나 disk 문제인가?
```

애플리케이션 metric만 보면 "느려졌다"는 사실은 알 수 있지만, 어느 계층에서 시작된 문제인지 구분하기 어렵다. 그래서 추가 운영 확장 Phase에서는 metric 범위를 API 내부에서 인프라 계층까지 넓히는 것을 목표로 잡았다.

## 2. 처음 세운 가설

처음에는 `/metrics`에 더 많은 custom metric을 추가하면 충분할 것이라고 생각할 수 있다. 하지만 API 프로세스가 알고 있는 정보에는 한계가 있다. Linux CPU steal, container memory limit, PostgreSQL lock wait, Redis evicted key, Nginx upstream latency는 API 코드만으로 정확히 알기 어렵다.

그래서 metric을 다음처럼 나누는 방향으로 설계했다.

| 계층 | 확인할 질문 |
|---|---|
| API | 요청이 실패했는가, p95/p99가 증가했는가 |
| Nginx | upstream에서 지연되는가, 5xx가 어디서 발생하는가 |
| PostgreSQL | connection/lock/transaction이 병목인가 |
| Redis | fallback이 Redis 장애 때문인가, cache miss 때문인가 |
| Container | memory limit, restart, CPU throttling이 있는가 |
| Linux Host | CPU, memory, disk, load average가 정상인가 |

## 3. exporter를 붙이는 이유

추가할 exporter는 단순히 dashboard를 예쁘게 만들기 위한 것이 아니다. 장애 원인을 계층별로 좁히기 위한 도구다.

- node-exporter: 서버 CPU, memory, disk, load average
- cAdvisor: container CPU throttling, memory limit, restart count
- postgres-exporter: connection count, lock wait, transaction 상태
- redis-exporter: connected clients, memory usage, evicted keys
- nginx-prometheus-exporter: status code, active connection, upstream 상태

이렇게 나누면 p99가 튀었을 때 바로 API 코드만 의심하지 않아도 된다. 예를 들어 API p99와 Nginx upstream time이 함께 증가하지만 DB lock wait도 증가했다면, 원인은 Nginx가 아니라 DB transaction 쪽일 가능성이 높다.

## 4. Grafana dashboard를 어떻게 나눌 것인가

하나의 dashboard에 모든 지표를 넣으면 처음 보기에는 편하지만 장애 상황에서는 오히려 흐름이 흐려진다. 그래서 dashboard를 API, Infra, PostgreSQL, Redis, Nginx로 분리하는 방향이 더 낫다고 봤다.

운영자가 처음 보는 화면은 API dashboard다. 여기서 error rate, p95/p99, Redis fallback count, DB retry count를 본다. 이상이 보이면 다음 계층 dashboard로 내려간다.

```text
API p99 증가
  -> Nginx upstream latency 확인
  -> DB connection/lock wait 확인
  -> Redis fallback/latency 확인
  -> container/host resource 확인
```

## 5. 트레이드오프

exporter를 늘리면 관측 범위는 넓어진다. 하지만 Prometheus target, dashboard, alert rule도 함께 늘어난다. 잘못된 alert threshold는 운영자를 피곤하게 만들고, 너무 많은 dashboard는 실제 장애 원인을 찾는 속도를 늦출 수 있다.

그래서 이 Phase의 기준은 "모든 지표를 다 모은다"가 아니라 "장애 원인 분리에 필요한 지표부터 모은다"이다.

## 6. 완료 기준

기획상 완료 기준은 다음 명령으로 정의한다.

```bash
make infra-up
make metrics-check
make dashboard-check
```

`metrics-check`는 Prometheus target이 모두 UP인지 확인하고, `dashboard-check`는 Grafana에서 API/Infra/DB/Redis/Nginx dashboard가 provision되었는지 확인한다.

## 7. 남은 한계

로컬 Docker Compose exporter 구성은 운영 환경의 multi-node, managed DB, cloud load balancer를 완전히 대체하지 못한다. 그래도 API metric만 보던 상태에서 인프라 계층까지 관측 범위를 넓히면, 장애 원인 분리의 기준이 훨씬 명확해진다.
