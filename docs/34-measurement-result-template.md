# Measurement Result Template

## 1. 목적

이 문서는 Ops Phase 구현 후 측정 결과를 같은 형식으로 기록하기 위한 템플릿이다.

측정 결과는 성능 수치, 장애 전후 비교, 정합성 검증, DR Drill 결과를 함께 남긴다.

## 2. Normal Load 결과

| Metric | Value |
|---|---:|
| RPS/TPS | TBD |
| p50 | TBD |
| p95 | TBD |
| p99 | TBD |
| 4xx rate | TBD |
| 5xx rate | TBD |
| timeout count | TBD |
| duplicate ledger count | 0 |

## 3. Peak Load 결과

| Metric | Value |
|---|---:|
| RPS/TPS | TBD |
| p50 | TBD |
| p95 | TBD |
| p99 | TBD |
| API CPU | TBD |
| DB active connection | TBD |
| Redis fallback count | TBD |
| Nginx upstream latency | TBD |
| duplicate ledger count | 0 |

## 4. Duplicate Storm 결과

| Metric | Value |
|---|---:|
| Fixed idempotency key requests | TBD |
| accepted/replayed/conflict response count | TBD |
| p95 | TBD |
| p99 | TBD |
| duplicate ledger count | 0 |
| duplicate external event count | 0 |
| orphan idempotency count | 0 |

## 5. Redis Down 결과

| Metric | Normal | Redis Down | 해석 |
|---|---:|---:|---|
| redis_up | TBD | 0 | Redis 장애 탐지 |
| redis_fallback_total | TBD | TBD | fallback 동작 |
| API p95 | TBD | TBD | degraded latency |
| API p99 | TBD | TBD | tail latency |
| DB retry count | TBD | TBD | DB 부하 전이 |
| duplicate ledger count | 0 | 0 | 정합성 유지 |

## 6. DB Pressure 결과

| Metric | Value |
|---|---:|
| active connection count | TBD |
| DB pool wait | TBD |
| transaction rollback count | TBD |
| lock wait | TBD |
| deadlock count | TBD |
| slow query count | TBD |
| API p99 | TBD |
| 5xx rate | TBD |

## 7. Nginx Burst / Rate Limit 결과

| Metric | Rate Limit Off | Rate Limit On | 해석 |
|---|---:|---:|---|
| Incoming RPS | TBD | TBD | 동일 burst 부하 |
| Upstream forwarded RPS | TBD | TBD | API 보호 여부 |
| 429 count | 0 | TBD | 제한 동작 |
| API CPU | TBD | TBD | upstream 부하 |
| API p99 | TBD | TBD | tail latency |
| 5xx rate | TBD | TBD | 장애 확산 |

## 8. DR Drill 결과

| Metric | Value |
|---|---:|
| backup duration | TBD |
| backup file size | TBD |
| checksum result | TBD |
| restore duration | TBD |
| RTO actual | TBD |
| RPO assumption | TBD |
| duplicated ledger count | 0 |
| balance mismatch count | 0 |
| orphan idempotency count | 0 |

## 9. 정합성 검증 SQL 결과

| Check | Expected | Actual | Result |
|---|---:|---:|---|
| duplicate ledger count | 0 | TBD | TBD |
| account balance mismatch | 0 | TBD | TBD |
| invalid state transition | 0 | TBD | TBD |
| orphan idempotency record | 0 | TBD | TBD |
| stale processing event | 0 | TBD | TBD |

## 10. 첨부 자료

| Evidence | Path |
|---|---|
| Normal dashboard | `docs/images/grafana/01-normal-baseline-dashboard.png` |
| Peak dashboard | `docs/images/grafana/02-peak-load-dashboard.png` |
| Redis down dashboard | `docs/images/grafana/03-redis-down-dashboard.png` |
| Prometheus targets | `docs/images/grafana/08-prometheus-targets-up.png` |
| k6 normal summary | `reports/k6/normal-load-summary.json` |
| DR Drill report | `reports/dr-drill/backup-restore-result.md` |
