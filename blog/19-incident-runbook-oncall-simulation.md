# 19편. 장애 Runbook을 작성하면서 배운 운영자의 사고방식

## 1. 문제를 어떻게 정의했는가

모니터링은 장애를 알려준다.
하지만 장애가 발생했을 때 운영자가 어떤 순서로 확인하고, 어떤 기준으로 복구 완료를 판단할지는 별도의 문서가 필요하다.

Runbook은 장애가 난 뒤 작성하는 문서가 아니라, 장애가 나기 전에 판단 순서를 고정하는 문서다.

## 2. Runbook 공통 구조

각 장애 문서는 다음 형식을 따른다.

```text
1. 증상
2. 사용자 영향
3. 즉시 확인할 지표
4. 확인 명령
5. 1차 대응
6. 복구 확인 기준
7. 재발 방지
8. 사후 기록 템플릿
```

이 구조를 고정하면 장애마다 문서 형식이 달라지는 문제를 줄일 수 있다.

## 3. Redis Down Runbook

Redis 장애는 정합성 장애가 아니다. PostgreSQL이 살아 있으면 API는 degraded mode로 처리할 수 있다.

확인할 지표는 다음과 같다.

- `financial_redis_operation_failed_total`
- `financial_redis_fallback_total`
- `financial_db_transaction_retry_total`
- p95/p99 latency

복구 기준은 Redis가 다시 살아나는 것만이 아니다. 중복 ledger가 0건인지 확인해야 한다.

## 4. DB Connection Exhaustion Runbook

PostgreSQL은 Source of Truth다. DB connection 고갈은 Redis 장애와 다르게 hard dependency 장애로 봐야 한다.

확인 순서는 다음과 같다.

1. `/ready` 실패 여부
2. active connection count
3. slow query 또는 lock wait
4. API 5xx/503 증가
5. ledger/account 정합성

## 5. Nginx 5xx Spike Runbook

Nginx 5xx는 upstream 장애, config 문제, Blue-Green 전환 실패, API readiness 실패에서 발생할 수 있다.

전환 직후라면 먼저 active upstream과 deployment status를 확인한다.

```bash
make deploy-status
make deploy-smoke
make deploy-rollback
make deploy-verify
```

DB rollback은 자동으로 하지 않는다. Phase 12 기준 rollback은 API traffic rollback이다.

## 6. p99 Latency Spike Runbook

p99만 튀는 상황은 평균 지연보다 더 어렵다. 일부 요청에서 DB lock wait, Redis fallback, Nginx upstream 지연, container throttling이 발생했을 수 있다.

그래서 p99 Runbook은 API metric에서 시작해 DB, Redis, Nginx, container resource 순서로 내려간다.

## 7. Failed Deployment Runbook

Green 검증 실패는 사용자 영향 없이 멈춰야 한다. 전환 후 실패는 즉시 Blue rollback을 수행하고, rollback 후 smoke와 정합성 검증을 실행한다.

복구 완료 기준은 다음과 같다.

- active upstream이 Blue로 복구
- `/health`, `/ready` 200
- deploy-smoke 통과
- duplicate ledger/event count 0

## 8. 남은 한계

Runbook은 실제 장애를 대신 해결하지 않는다.
하지만 장애 순간에 어떤 지표를 보고, 어떤 명령을 실행하고,
어떤 기준으로 복구를 선언할지 미리 정리해두면 대응 속도와 일관성이 크게 좋아진다.

## 9. 실제 구현 후 보강할 내용

이 글은 Ops Phase 7 구현 전 설계 초안이다. 구현 후에는 다음 내용을 추가한다.

- 각 장애 drill 명령 실행 결과
- alert firing 캡처 또는 Prometheus API 결과
- runbook 절차대로 복구한 기록
- 복구 후 `make k6-verify` 또는 정합성 SQL 결과
- `reports/incidents/{scenario}/result.md` 예시
