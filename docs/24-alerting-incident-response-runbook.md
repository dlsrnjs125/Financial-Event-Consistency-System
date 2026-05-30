# Ops Phase 6 - Alerting & Incident Response Runbook

## 왜 Alert Rule과 Runbook이 필요한가

Ops Phase 4와 5는 복구 가능성과 복구 절차를 검증했다.
Ops Phase 6의 목적은 한 단계 더 앞선다. 장애가 발생했을 때 운영자가 무엇을
장애로 볼지, warning과 critical을 어떻게 나눌지, 어떤 순서로 확인하고 대응할지
Prometheus Alert Rule과 Incident Response Runbook으로 고정한다.

Alert는 단순 threshold가 아니라 운영자가 행동할 수 있는 신호여야 한다.
따라서 각 rule은 `severity`, `component`, `runbook`, `impact`, `action`을 함께
가진다.

## Alert Severity 기준

| Severity | 의미 | 예시 | 대응 시간 |
|---|---|---|---|
| warning | 즉시 데이터 정합성 사고는 아니지만 부하 전이 또는 장애 확산 가능성이 있다. | Redis down, p95 latency 상승 | 업무 시간 내 즉시 확인 |
| critical | 사용자 요청 실패 또는 Source of Truth/정합성 위험이 있다. | API down, PostgreSQL down, reconciliation failure | 즉시 대응 |

## Alert Inventory

| Alert | 조건 | Severity | 사용자 영향 | 정합성 영향 | 1차 대응 |
|---|---|---|---|---|---|
| FinancialApiDown | API target `up == 0` | critical | 신규 요청 실패 가능 | 재시도 증가로 중복 요청 압력 증가 | API/Nginx 상태 확인 후 health/ready/smoke |
| FinancialApiHighErrorRate | 5xx 비율 1% 초과 | critical | 외부 시스템 재시도 증가 | partial failure 여부 확인 필요 | trace 로그, DB readiness, smoke, consistency 확인 |
| FinancialApiHighLatencyP95 | p95 latency 500ms 초과 | warning | 응답 지연 | timeout/retry 증가 가능 | API/Redis/DB 부하 확인 |
| FinancialRedisDown | Redis exporter target down, `redis_up == 0`, 또는 Redis readiness degraded | warning | cache/lock 성능 저하 | PostgreSQL 기준 정합성은 유지되어야 함 | fallback metric, DB retry, Ops5 Redis drill 연결 |
| FinancialPostgresDown | `pg_up == 0` 또는 PostgreSQL readiness failed | critical | 신규 거래 처리 중단 | Source of Truth 장애 | DB 복구, readiness 확인, consistency SQL |
| FinancialInvalidStateTransitionDetected | invalid state transition 증가 | critical | 일부 이벤트 실패 | 상태 전이 정책/이벤트 순서 위험 | 이벤트 흐름 추적, 상태 이력 확인 |
| FinancialReconciliationFailureDetected | 최근 5분 내 reconciliation failure 증가 | critical | 서비스 중단 검토 | 금융 정합성 사고 가능성 | 트래픽 제한, evidence 보존, 정합성 SQL 실행 |

## API 장애 대응 Runbook

1. `FinancialApiDown` 또는 `FinancialApiHighErrorRate` alert를 확인한다.
2. `make local-status`로 `api-blue`, `nginx`, `postgres`, `redis` 상태를 본다.
3. `curl -i http://localhost:8080/health`와 `curl -i http://localhost:8081/ready`를 확인한다.
4. 최근 배포가 있다면 `make deploy-status`와 `make deploy-rollback` 가능성을 확인한다.
5. `make deploy-smoke`로 거래 처리 경로가 살아 있는지 확인한다.
6. 복구 후 `make deploy-verify` 또는 consistency SQL을 실행한다.

## Redis 장애 대응 Runbook

Redis는 cache/lock 계층이다. PostgreSQL이 정상이라면 최종 정합성은 유지되어야 한다.
따라서 Redis down은 기본적으로 warning이다.

1. `FinancialRedisDown` alert를 확인한다.
2. `/ready`에서 Redis가 degraded인지 확인한다.
3. `financial_redis_fallback_total`, `financial_redis_operation_failed_total`, `financial_db_transaction_retry_total` 증가를 확인한다.
4. DB 부하가 커지면 duplicate storm과 lock contention 가능성을 함께 본다.
5. `make ops5-redis-drill` 또는 `make ops5-demo`로 복구 절차와 중복 ledger 0건을 확인한다.

## PostgreSQL 장애 대응 Runbook

PostgreSQL은 Source of Truth다. PostgreSQL 장애는 degraded mode가 아니라 critical이다.

1. `FinancialPostgresDown` alert를 확인한다.
2. `/ready`가 503 또는 postgres failed인지 확인한다.
3. 운영 DB volume 삭제나 `docker compose down -v` 같은 destructive command를 사용하지 않는다.
4. `make failure-db-up` 또는 안전한 DB 재기동 절차를 수행한다.
5. 복구 후 `/ready` PASS를 확인한다.
6. `make k6-verify` 또는 `scripts/sql/dr_consistency_check.sql` 계열 count-only SQL을 실행한다.

## 정합성 위반 의심 대응 Runbook

정합성 alert는 availability alert보다 더 심각하게 취급한다.

1. 신규 이벤트 유입을 제한할 필요가 있는지 판단한다.
2. `trace_id`, `request_id`, masked idempotency key 기준으로 관련 로그를 보존한다.
3. 중복 event, 중복 ledger, orphan ledger, completed event without ledger, account balance mismatch count를 확인한다.
4. `reports/ops`와 `reports/dr` evidence를 보존한다.
5. 원인 분석 전 LedgerEntry를 삭제하지 않는다. CANCEL은 보정 거래로만 처리한다.

## CI에서 검증하는 것

- alert rule 파일 존재
- `scripts/ops6_alert_rule_validation.sh` 문법과 실행 권한
- YAML 구조와 required alert inventory
- `promtool check rules`
- generated report의 주요 섹션과 required alert count

CI에서는 monitoring stack 전체 기동과 Prometheus API rule load check를 수행하지 않는다.
컨테이너 기동 타이밍과 runner 상태에 따른 flakiness를 줄이기 위해 API load check는
로컬 `make ops6-demo`에서 검증한다.

## 로컬에서 검증하는 것

```bash
make ops6-up
make ops6-check
make ops6-alert-rules
make ops6-drill
make ops6-demo
```

로컬에서는 Prometheus API `/api/v1/rules`를 호출해 required alert rules가 실제로
로드되었는지 확인한다. `PROMETHEUS_API_CHECK=true`에서 Prometheus API가 내려가
있거나 required alert가 로드되지 않았으면 `make ops6-demo`는 FAIL로 끝난다.

## 운영상 한계와 보완 전략

- Alertmanager, Slack, PagerDuty 실연동은 이번 Phase에서 제외한다.
- Redis down은 warning으로 둔다. PostgreSQL 기준 정합성이 유지되는지와 DB 부하 전이를 함께 본다.
- PostgreSQL down은 critical이다. Source of Truth 장애이므로 신규 거래 처리를 중단하거나 제한할 수 있다.
- duplicate ledger count와 idempotency violation count는 현재 Prometheus gauge가 아니라 SQL/report evidence 중심이다. 후속 Phase에서 bounded application gauge를 추가할 수 있다.
- `FinancialReconciliationFailureDetected`는 counter 누적값 전체가 아니라 `increase(financial_reconciliation_failures_total[5m]) > 0`으로 최근 발생을 감지한다. 장애가 현재도 active인지 표현하려면 후속 Phase에서 active gauge를 추가해야 한다.
- Ops6 alert rule의 canonical source는 `infra/prometheus/rules/financial_event_alerts.yml`이다. 기본 Compose와 monitoring Compose는 이 파일을 각각 필요한 컨테이너 내부 경로로 mount한다.
- promtool fallback Docker image는 `prom/prometheus:v2.54.1`로 고정해 rule 검증 재현성을 높인다. 운영 Prometheus 버전을 바꾸면 이 값도 함께 맞춘다.
- 운영 임계값은 로컬 측정값 기준의 초안이다. 장시간 운영 데이터가 쌓이면 조정해야 한다.

## Troubleshooting

- 기존 metric 이름이 문서와 다르면 `backend/app/observability/metrics.py`의 실제 이름을 기준으로 alert expression을 조정한다.
- `promtool check rules`가 실패하면 PromQL metric label과 histogram bucket 이름을 확인한다.
- Prometheus API rule load check가 FAIL이면 monitoring stack이 실행 중인지, `make ops6-up`을 먼저 실행했는지 확인한다.
- Prometheus API rule load check가 SKIPPED이면 CI처럼 `PROMETHEUS_API_CHECK=false`로 실행된 것이다.
- CI에서 Prometheus API load check를 제외한 것은 의도적 trade-off다. CI는 rule 문법, required inventory, report 형식을 검증하고, 실제 rule load evidence는 `reports/ops/ops6-alerting-incident-runbook.md`에 로컬 실행 결과로 남긴다.
- Alertmanager route와 receiver는 이번 Phase에서 실제 운영 연동하지 않는다. secret/token 없이 rule과 runbook 기준만 검증한다.
