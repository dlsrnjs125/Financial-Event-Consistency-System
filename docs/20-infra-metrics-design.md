# Infra Metrics Design

## 1. 목적

기존 `/metrics` 중심의 애플리케이션 metric만으로는 장애 원인이 API 로직인지, DB connection 고갈인지, Redis 장애인지, 서버 리소스 부족인지 구분하기 어렵다. Infra Metrics Extension은 관측 범위를 API에서 Linux, container, PostgreSQL, Redis, Nginx 계층으로 확장한다.

## 2. 추가 exporter 설계

| Exporter | 목적 | 주요 지표 |
|---|---|---|
| node-exporter | 서버 리소스 | CPU, memory, disk, load average |
| cAdvisor | container 상태 | CPU throttling, memory limit, restart count |
| postgres-exporter | DB 상태 | connection count, lock wait, slow query |
| redis-exporter | Redis 상태 | connected clients, memory usage, evicted keys |
| nginx-prometheus-exporter | Proxy 상태 | 2xx/4xx/5xx, active connection, upstream 지표 |

## 3. Dashboard 분리

| Dashboard | 확인할 질문 |
|---|---|
| API | 요청량, error rate, p95/p99, Redis fallback |
| Infra | CPU, memory, disk, container restart |
| PostgreSQL | connection, lock, transaction duration |
| Redis | memory, evicted key, command latency |
| Nginx | status code, upstream latency, rate limit hit |

## 4. Makefile 목표

```bash
make infra-up
make metrics-check
make dashboard-check
```

`metrics-check`는 Prometheus target이 모두 UP인지 확인하고, `dashboard-check`는 Grafana dashboard provision 상태를 확인한다.

## 5. README 요약 문장

기존 애플리케이션 메트릭만으로는 장애 원인이 API 로직인지, DB 커넥션 고갈인지, Redis 장애인지, 서버 리소스 부족인지 구분하기 어렵다고 판단했다. 따라서 node-exporter, postgres-exporter, redis-exporter, nginx exporter를 추가해 금융 이벤트 처리 시스템의 운영 관측 범위를 애플리케이션에서 인프라 계층까지 확장한다.
