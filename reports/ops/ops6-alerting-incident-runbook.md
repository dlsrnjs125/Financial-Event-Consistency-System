# Ops Phase 6 - Alerting & Incident Response Runbook

## 실행 목적

Prometheus Alert Rule과 Incident Response Runbook을 구성하고, API/Redis/PostgreSQL/정합성 장애의 탐지 기준과 운영자 1차 대응 기준을 evidence로 남긴다.

## 검증 환경

| 항목 | 값 |
|---|---|
| 검증 시각 UTC | `2026-05-30T18:38:58Z` |
| Alert rule file | `infra/prometheus/rules/financial_event_alerts.yml` |
| Prometheus URL | `http://localhost:9090` |
| Prometheus API check | `true` |

## Alert Rule 검증 결과

| 항목 | 결과 |
|---|---|
| Alert rule file exists | PASS |
| YAML parse | PASS |
| promtool check rules | PASS |
| Prometheus rule load check | PASS |
| Required alert count | 7 |
| Overall result | PASS |

Prometheus rule load note: Required alert rules are loaded in Prometheus.

## Required Alert Inventory

| Alert | Severity | Component | Runbook |
|---|---|---|---|
| FinancialApiDown | critical | api | `docs/24-alerting-incident-response-runbook.md` |
| FinancialApiHighErrorRate | critical | api | `docs/24-alerting-incident-response-runbook.md` |
| FinancialApiHighLatencyP95 | warning | api | `docs/24-alerting-incident-response-runbook.md` |
| FinancialRedisDown | warning | redis | `docs/24-alerting-incident-response-runbook.md` |
| FinancialPostgresDown | critical | postgres | `docs/24-alerting-incident-response-runbook.md` |
| FinancialInvalidStateTransitionDetected | critical | consistency | `docs/24-alerting-incident-response-runbook.md` |
| FinancialReconciliationFailureDetected | critical | consistency | `docs/24-alerting-incident-response-runbook.md` |

## CI 검증 범위

CI는 alert rule 파일 존재, 스크립트 문법, YAML 구조, `promtool check rules`, report 주요 문구를 검증한다.
Prometheus API rule load check는 runner timing과 monitoring stack 기동 비용 때문에 CI에서는 `PROMETHEUS_API_CHECK=false`로 SKIPPED를 허용한다.

## Local 검증 범위

로컬에서는 `make ops6-demo`로 monitoring stack을 기동한 뒤 Prometheus API에서 required alert rule load 여부까지 확인한다.

## 운영상 한계와 보완 전략

- Slack/PagerDuty/Alertmanager 실연동은 이번 Phase에서 제외한다.
- Redis down은 PostgreSQL 기준 최종 정합성 실패가 아니므로 warning으로 분류한다.
- PostgreSQL down은 Source of Truth 장애이므로 critical로 분류한다.
- consistency violation은 availability 장애보다 더 높은 금융 도메인 위험으로 취급한다.

## Troubleshooting

- Prometheus API rule load check가 SKIPPED이면 monitoring stack이 실행 중인지, `make ops6-up`을 먼저 실행했는지 확인한다.
- `promtool check rules`가 실패하면 alert expression metric 이름과 label 이름이 현재 `backend/app/observability/metrics.py`와 일치하는지 확인한다.
- 현재 duplicate ledger count와 idempotency violation count는 report/SQL evidence로 검증하며, 직접 gauge metric은 후속 Phase에서 추가한다.

## README에 기록할 문장

Ops Phase 6에서는 Prometheus Alert Rule과 Incident Response Runbook을 구성하고, API/Redis/PostgreSQL/정합성 장애의 탐지 기준과 1차 대응 절차를 evidence report로 남긴다.
