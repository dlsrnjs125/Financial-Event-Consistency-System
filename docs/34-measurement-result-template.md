# Measurement Result Template

## 1. 목적

이 문서는 Ops Phase 구현 후 측정 결과를 같은 형식으로 기록하기 위한 템플릿이다.

측정 결과는 성능 수치, 장애 전후 비교, 정합성 검증, DR Drill 결과를 함께 남긴다.

## 2. 측정 환경

모든 결과는 동일 조건에서 재현 가능하도록 측정 환경을 먼저 기록한다.

| 항목 | 기록 값 |
|---|---|
| 실행 일시 | TBD |
| Git commit SHA | TBD |
| 실행 브랜치 | TBD |
| OS/Architecture | TBD |
| Docker version | TBD |
| Docker Compose version | TBD |
| API worker 수 | TBD |
| PostgreSQL max connections | TBD |
| SQLAlchemy pool size | TBD |
| Redis 설정 | TBD |
| Nginx rate limit 설정 | TBD |
| k6 VUs / duration | TBD |
| 테스트 데이터 규모 | TBD |

## 3. 측정값 해석 기준

수치는 기록만으로 충분하지 않다.
아래 기준으로 정상, Warning, Critical을 구분한다.

| 지표 | 정상 | Warning | Critical |
|---|---:|---:|---:|
| API 5xx rate | < 1% | 1~3% | >= 3% |
| API p95 | < 300ms | 300~500ms | >= 500ms |
| API p99 | < 1s | 1~2s | >= 2s |
| DB connection usage | < 70% | 70~90% | >= 90% |
| Redis fallback rate | 낮음 | 급증 | 지속 급증 + p99 상승 |
| Disk usage | < 80% | 80~90% | >= 90% |
| 정합성 위반 | 0 | 없음 | >= 1 |
| DR restore success | 성공 | 지연 | 실패 |

정합성 위반은 일반적인 성능 저하와 다르게 error budget을 두지 않는다.
`duplicate ledger`, `account balance mismatch`, `invalid state transition`,
`orphan idempotency record`가 1건이라도 발생하면 Critical로 기록한다.

## 4. Normal Load 결과

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

## 5. Peak Load 결과

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

## 6. Duplicate Storm 결과

| Metric | Value |
|---|---:|
| Fixed idempotency key requests | TBD |
| accepted/replayed/conflict response count | TBD |
| p95 | TBD |
| p99 | TBD |
| duplicate ledger count | 0 |
| duplicate external event count | 0 |
| orphan idempotency count | 0 |

## 7. Redis Down 결과

| Metric | Normal | Redis Down | 해석 |
|---|---:|---:|---|
| redis_up | TBD | 0 | Redis 장애 탐지 |
| redis_fallback_total | TBD | TBD | fallback 동작 |
| API p95 | TBD | TBD | degraded latency |
| API p99 | TBD | TBD | tail latency |
| DB retry count | TBD | TBD | DB 부하 전이 |
| duplicate ledger count | 0 | 0 | 정합성 유지 |

## 8. DB Pressure 결과

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

## 9. Nginx Burst / Rate Limit 결과

| Metric | Rate Limit Off | Rate Limit On | 해석 |
|---|---:|---:|---|
| Incoming RPS | TBD | TBD | 동일 burst 부하 |
| Upstream forwarded RPS | TBD | TBD | API 보호 여부 |
| 429 count | 0 | TBD | 제한 동작 |
| API CPU | TBD | TBD | upstream 부하 |
| API p99 | TBD | TBD | tail latency |
| 5xx rate | TBD | TBD | 장애 확산 |

## 10. DR Drill 결과

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

## 11. 정합성 검증 SQL 결과

| Check | Expected | Actual | Result |
|---|---:|---:|---|
| duplicate ledger count | 0 | TBD | TBD |
| account balance mismatch | 0 | TBD | TBD |
| invalid state transition | 0 | TBD | TBD |
| orphan idempotency record | 0 | TBD | TBD |
| stale processing event | 0 | TBD | TBD |

## 12. 성공/실패 판정

| 항목 | 성공 기준 | 실패 기준 | Result |
|---|---|---|---|
| Prometheus target | 필수 target 모두 UP | 필수 target 1개 이상 DOWN | TBD |
| Grafana capture | timestamp/scenario/핵심 지표 포함 | 핵심 지표 누락 | TBD |
| k6 summary | JSON 파일 생성 | summary 저장 실패 | TBD |
| Redis degraded | `redis_up=0`, fallback 증가, 정합성 0건 | fallback 실패 또는 5xx 확산 | TBD |
| DB pressure | connection/lock/p99 관측 | DB 장애 원인 분류 불가 | TBD |
| Nginx rate limit | 429 증가와 upstream 보호 확인 | API 5xx 확산 | TBD |
| DR Drill | checksum/restore/SQL 검증 성공 | restore 또는 checksum 실패 | TBD |
| 정합성 | 위반 0건 | 위반 >= 1건 | TBD |

## 13. 첨부 자료

| Evidence | Path |
|---|---|
| Normal dashboard | `docs/images/grafana/01-normal-baseline-dashboard.png` |
| Peak dashboard | `docs/images/grafana/02-peak-load-dashboard.png` |
| Redis down dashboard | `docs/images/grafana/03-redis-down-dashboard.png` |
| Prometheus targets | `docs/images/grafana/08-prometheus-targets-up.png` |
| k6 normal summary | `reports/k6/normal-load-summary.json` |
| DR Drill report | `reports/dr-drill/backup-restore-result.md` |
