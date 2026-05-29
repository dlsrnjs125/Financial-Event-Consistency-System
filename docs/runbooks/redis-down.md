# Redis Down Runbook

## 1. 장애 정의

Redis connection error, timeout, container down, network error로 인해 Redis lock/cache 계층을 사용할 수 없는 상태다.

Redis는 성능 최적화 계층이므로 PostgreSQL이 정상이라면 API는 degraded mode로 계속 처리해야 한다.

## 2. 사용자 영향

- idempotency cache replay 속도 저하
- duplicate request storm에서 DB 부하 증가 가능
- 최종 정합성은 PostgreSQL transaction과 unique constraint 기준으로 유지되어야 함

## 3. 즉시 확인할 Dashboard

- API dashboard: p95/p99, 5xx rate, Redis fallback count
- Redis dashboard: `redis_up`, connected clients, memory
- PostgreSQL dashboard: connection count, retry count

## 4. Alert Rule

```yaml
annotations:
  runbook: "docs/runbooks/redis-down.md"
```

확인할 alert:

- `RedisDownButApiAlive`
- `RedisFallbackIncreasing`
- `ApiHighP99Latency`

## 5. 1차 확인 명령

```bash
make failure-status
curl -i http://localhost:8000/ready
make k6-verify
```

## 6. 원인 분기표

| 관측 결과 | 판단 | 대응 |
|---|---|---|
| `redis_up=0`, API 200 | degraded mode 정상 | fallback 증가 추적 |
| `redis_up=0`, API 5xx 증가 | fallback 실패 | API Redis 예외 처리 확인 |
| fallback 증가, DB retry 증가 | DB 부하 전이 | DB connection/lock 확인 |
| Redis 복구 후 fallback 지속 | client reconnect 문제 | API Redis connection pool 확인 |

## 7. 대응 절차

1. Redis container 상태 확인
2. API가 degraded mode로 동작하는지 확인
3. duplicate storm 테스트 또는 DB 검증 SQL로 중복 반영 0건 확인
4. Redis 복구
5. cache warm-up 필요 여부 확인

## 8. 복구 확인 기준

- `/ready`에서 Redis 상태 정상 또는 degraded 해소
- Redis fallback 증가 중단
- 중복 ledger 0건
- p95/p99가 Redis 장애 이전 수준으로 회복

## 9. 재발 방지

- Redis exporter와 alert rule 추가
- lock rejected와 Redis failure metric 분리 유지
- Redis 장애 drill 정기 실행

## 10. 사후 기록 템플릿

- 발생 시간:
- Redis 상태:
- fallback 증가량:
- 중복 ledger 검증 결과:
- 복구 시간:
- 재발 방지 작업:
