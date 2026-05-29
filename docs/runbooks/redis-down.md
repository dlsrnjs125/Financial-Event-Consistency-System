# Redis Down Runbook

## 1. 증상

- `/ready`에서 `redis=degraded`
- `financial_redis_fallback_total` 증가
- p95/p99 응답시간 상승 가능

## 2. 사용자 영향

중복 요청 완화 성능과 idempotency cache replay 속도가 저하될 수 있다. 단, PostgreSQL transaction과 unique constraint 기준 최종 정합성은 유지되어야 한다.

## 3. 즉시 확인할 지표

- `financial_redis_operation_failed_total`
- `financial_redis_fallback_total`
- `financial_db_transaction_retry_total`
- `financial_http_request_duration_seconds` p95/p99

## 4. 확인 명령

```bash
make failure-status
curl -i http://localhost:8000/ready
make k6-verify
```

## 5. 1차 대응

1. Redis container 상태 확인
2. API가 degraded mode로 동작하는지 확인
3. duplicate storm 테스트 또는 DB 검증 SQL로 중복 반영 0건 확인
4. Redis 복구
5. cache warm-up 필요 여부 확인

## 6. 복구 확인 기준

- `/ready`에서 Redis 상태가 정상 또는 degraded 해소
- Redis fallback 증가 중단
- 중복 ledger 0건
- p95/p99가 Redis 장애 이전 수준으로 회복

## 7. 재발 방지

- Redis exporter와 alert rule 추가
- lock rejected와 Redis failure metric 분리 유지
- Redis 장애 훈련을 정기적으로 실행

## 8. 사후 기록 템플릿

- 발생 시간:
- Redis 상태:
- fallback 증가량:
- 중복 ledger 검증 결과:
- 복구 시간:
- 재발 방지 작업:
