# High Latency p99 Runbook

## 1. 증상

- p99 latency 급증
- p95는 정상인데 일부 요청만 크게 지연
- Redis fallback 또는 DB lock wait 증가 가능

## 2. 사용자 영향

일부 금융 이벤트 요청이 timeout되고 client retry가 증가할 수 있다. retry 증가는 duplicate request storm으로 이어질 수 있으므로 idempotency 처리 상태를 함께 확인한다.

## 3. 즉시 확인할 지표

- `financial_http_request_duration_seconds` p95/p99
- DB transaction duration
- Redis fallback count
- Nginx upstream response time
- container CPU throttling

## 4. 확인 명령

```bash
make k6-smoke
make k6-verify
curl -s http://localhost:8000/metrics
```

## 5. 1차 대응

1. p95와 p99 차이 확인
2. DB connection/lock wait 확인
3. Redis fallback 증가 여부 확인
4. Nginx upstream latency 확인
5. duplicate ledger/event count 확인

## 6. 복구 확인 기준

- p99가 기준 이하로 회복
- 5xx 증가 없음
- duplicate count 0
- Redis fallback 또는 DB retry 증가 중단

## 7. 재발 방지

- p99 alert threshold 조정
- DB slow query와 lock wait dashboard 추가
- duplicate storm과 peak load를 분리 측정

## 8. 사후 기록 템플릿

- 발생 시간:
- p95/p99 peak:
- DB/Redis/Nginx 이상 여부:
- 사용자 영향:
- 재발 방지:
