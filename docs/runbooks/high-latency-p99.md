# High Latency p99 Runbook

## 1. 장애 정의

p99 latency가 기준치를 초과해 일부 요청이 timeout 또는 매우 긴 지연을 겪는 상태다.

p95는 정상인데 p99만 튀는 경우 일부 요청에만 영향을 주는 병목을 의심한다.
예를 들면 DB lock wait, Redis fallback, Nginx upstream 지연, container throttling이 있다.

## 2. 사용자 영향

- 일부 금융 이벤트 요청 timeout
- client retry 증가
- duplicate request storm 가능성 증가
- Redis/DB fallback 경로 부하 증가

## 3. 즉시 확인할 Dashboard

- API dashboard: p95/p99, error rate
- PostgreSQL dashboard: lock wait, transaction duration
- Redis dashboard: fallback, command latency
- Nginx dashboard: upstream response time
- Infra dashboard: CPU throttling, memory pressure

## 4. Alert Rule

```yaml
annotations:
  runbook: "docs/runbooks/high-latency-p99.md"
```

확인할 alert:

- `ApiHighP99Latency`
- `NginxUpstreamLatencyHigh`
- `PostgresLockWaitHigh`

## 5. 1차 확인 명령

```bash
make k6-smoke
make k6-verify
curl -s http://localhost:8081/metrics
```

## 6. 원인 분기표

| 관측 결과 | 판단 | 대응 |
|---|---|---|
| p99만 상승, p95 정상 | 일부 요청 병목 | trace/log 샘플 확인 |
| DB lock wait 증가 | DB row lock 병목 | long transaction 확인 |
| Redis fallback 증가 | Redis 장애 또는 timeout | Redis runbook 연결 |
| Nginx upstream time 증가 | upstream 지연 | API/DB 계층 확인 |
| CPU throttling 증가 | container resource 병목 | limit/부하 확인 |

## 7. 대응 절차

1. p95와 p99 차이 확인
2. DB connection/lock wait 확인
3. Redis fallback 증가 여부 확인
4. Nginx upstream latency 확인
5. duplicate ledger/event count 확인

## 8. 복구 확인 기준

- p99가 기준 이하로 회복
- 5xx 증가 없음
- duplicate count 0
- Redis fallback 또는 DB retry 증가 중단

## 9. 재발 방지

- p99 alert threshold 조정
- DB slow query와 lock wait dashboard 추가
- duplicate storm과 peak load를 분리 측정

## 10. 사후 기록 템플릿

- 발생 시간:
- p95/p99 peak:
- DB/Redis/Nginx 이상 여부:
- 사용자 영향:
- 재발 방지:
