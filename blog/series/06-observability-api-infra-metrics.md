# API p99가 느려졌을 때 코드 문제인지 DB 문제인지 어떻게 구분할까?

처음에는 FastAPI metric이면 충분하다고 생각했다. API p95/p99, request count, error count를 보면 장애를 설명할 수 있을 것 같았다. 하지만 p99 상승은 증상일 뿐 원인이 아니다.

## application metric만으로는 부족했다

API handler가 느린 것인지, Nginx edge 구간이 느린 것인지, PostgreSQL이 느린 것인지, Redis fallback이 늘어난 것인지 구분해야 했다.

그래서 관측 지표를 계층별로 나눴다.

- Nginx request/upstream timing
- FastAPI handler timing
- PostgreSQL connection/query signal
- Redis cache/lock/fallback signal
- container/host resource signal
- consistency counter

## 장애 원인을 좁히는 방식

Nginx request time은 높은데 upstream time이 정상이라면 application 내부보다 edge/client path를 의심한다. Handler와 PostgreSQL phase가 함께 높다면 DB pool, lock, query를 본다. Redis fallback이 증가하면 cache/lock 계층을 본다.

이 구조는 PH10 latency attribution으로 이어진다. p99를 원인으로 보지 않고, 어떤 계층의 evidence가 함께 상승했는지 본다.

## 아직 남긴 한계

OpenTelemetry full tracing과 Loki 기반 log query는 후속 후보로 남겼다. 이 단계에서는 Prometheus/Grafana와 structured log evidence로 "어디를 먼저 볼지"를 좁히는 데 집중했다.
