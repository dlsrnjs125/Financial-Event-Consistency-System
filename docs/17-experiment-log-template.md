# 17. Experiment Log Template

## 실험 제목

예시:

```text
Redis Cache 도입 전후 Idempotency 응답시간 비교
```

---

## 1. 실험 배경

이 실험을 수행한 이유를 작성한다.

예시:

동일 Idempotency-Key 재요청이 반복될 때 매번 DB를 조회하면 DB 부하가 증가할 수 있다.
Redis Cache를 사용하면 중복 요청에 대해 더 빠르게 기존 응답을 반환할 수 있을 것으로 예상했다.

---

## 2. 가설

Redis Cache를 사용하면 중복 요청의 p95 latency가 감소하고 DB query count가 줄어들 것이다.

단, Redis 장애 시에도 중복 반영률은 0%를 유지해야 한다.

---

## 3. 실험 환경

| 항목 | 값 |
|------|----|
| 날짜 |  |
| Commit |  |
| 실행 환경 |  |
| API worker |  |
| DB pool size |  |
| Redis 사용 여부 |  |
| k6 script |  |
| VUs |  |
| Duration |  |

---

## 4. 실험 조건

### A안

- Redis Cache 미사용
- IdempotencyRecord를 PostgreSQL에서 조회

### B안

- Redis Cache 사용
- Cache Hit 시 DB 조회 없이 기존 응답 반환

---

## 5. 측정 지표

- p50 latency
- p95 latency
- p99 latency
- `http_req_failed`
- `financial_idempotency_hit_total`
- `financial_events_duplicate_total`
- `financial_db_transaction_duration_seconds`
- `db_connections_active`
- `redis_keyspace_hits_total`
- `redis_keyspace_misses_total`

---

## 6. 결과

| 조건 | p50 | p95 | p99 | error rate | DB conn avg | cache hit ratio | duplicate rate |
|------|-----|-----|-----|------------|-------------|-----------------|----------------|
| A안 |  |  |  |  |  |  |  |
| B안 |  |  |  |  |  |  |  |

---

## 7. 분석

- p95가 감소했는가?
- p99가 악화되지는 않았는가?
- DB Connection 사용량이 줄었는가?
- Redis Cache Hit Ratio가 목표치에 도달했는가?
- 중복 반영률은 0%를 유지했는가?

---

## 8. 결론

이 실험 결과를 바탕으로 어떤 설계를 유지할지, 수정할지 결정한다.

---

## 9. 후속 작업

- 추가 테스트
- 코드 개선
- 메트릭 추가
- 블로그 반영
- README 수치 업데이트
