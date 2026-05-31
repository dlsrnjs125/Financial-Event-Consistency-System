# Ops Phase 7 - Incident Timeline & Postmortem Drill

## 실행 목적

Redis degraded incident를 재현하고, 장애 발생부터 탐지, 영향 확인, 복구, 정합성 검증, 원인 분석, 재발 방지 Action Item까지 count-only postmortem evidence로 남긴다.

## Incident Summary

| 항목 | 값 |
|---|---|
| Incident ID | OPS7-20260531T061517Z |
| Scenario | Redis degraded duplicate event handling |
| Severity | warning |
| Started at | 2026-05-31T06:15:18Z |
| Detected at | 2026-05-31T06:15:18Z |
| Mitigated at | 2026-05-31T06:15:19Z |
| Recovered at | 2026-05-31T06:15:20Z |
| Detection latency seconds | 0 |
| Mitigation latency seconds | 1 |
| Recovery duration seconds | 1 |
| Total incident duration seconds | 2 |
| Overall result | PASS |

## Incident Timeline

| Time UTC | Phase | Event | Evidence |
|---|---|---|---|
| 2026-05-31T06:15:18Z | STARTED | Incident drill started | incident_id=OPS7-20260531T061517Z |
| 2026-05-31T06:15:18Z | DETECTED | Redis degraded detected | readiness=degraded |
| 2026-05-31T06:15:19Z | IMPACT_CHECK | Duplicate smoke executed | first=200, second=200, event_prefix=OPS7-INCIDENT |
| 2026-05-31T06:15:19Z | MITIGATED | Redis restart requested | container=start |
| 2026-05-31T06:15:20Z | RECOVERED | Readiness recovered | ready=PASS |
| 2026-05-31T06:15:20Z | VERIFIED | Consistency check passed | duplicate_ledger_count=0 |

## Impact Evidence

| 항목 | 결과 |
|---|---|
| Redis degraded detected | PASS |
| API fallback behavior | PASS |
| First duplicate smoke status | 200 |
| Second duplicate smoke status | 200 |
| Synthetic external event id prefix | OPS7-INCIDENT |
| Synthetic idempotency key prefix | ops7-incident |
| Event count for duplicate smoke | 1 |
| Ledger count for duplicate smoke | 1 |
| Idempotency record count for duplicate smoke | 1 |
| Duplicate ledger count | 0 |
| Idempotency violation count | 0 |
| Consistency check | PASS |

## Root Cause Analysis

| 항목 | 내용 |
|---|---|
| Immediate cause | Redis container stopped by controlled drill |
| Root cause category | Dependency degraded |
| Source of truth impact | PostgreSQL consistency maintained |
| User impact | Duplicate event request accepted without duplicate ledger |
| Data consistency impact | No duplicate ledger, no idempotency violation |

## Recovery Verification

| 항목 | 결과 |
|---|---|
| Redis restarted | PASS |
| Health after recovery | PASS |
| Ready after recovery | PASS |
| Smoke after recovery | PASS |
| Consistency after recovery | PASS |

## Action Items

| 우선순위 | 항목 | 목적 | 후속 Phase |
|---|---|---|---|
| P1 | incident timeline을 Slack/PagerDuty/Jira ticket과 연결 | Markdown evidence를 실제 운영 incident workflow와 연결 | Ops follow-up |
| P2 | trace_id/request_id/event_id 기반 log query evidence 추가 | 원인 추적을 수동 report에서 queryable evidence로 확장 | OpenTelemetry/Loki follow-up |
| P2 | Redis degraded alert와 postmortem template 자동 연결 | Alert 발생 후 운영자가 같은 template으로 기록하도록 표준화 | Ops follow-up |

## 운영상 한계와 보완 전략

- 이 drill은 Docker Compose Redis stop/start로 controlled incident를 재현하며, destructive DB operation은 수행하지 않는다.
- Redis degraded는 warning 성격의 incident다. PostgreSQL Source of Truth가 유지되는지와 duplicate ledger 0건을 핵심 기준으로 삼는다.
- Report에는 실제 거래 row data, account_no 원문, secret, token을 기록하지 않고 PASS/FAIL, duration, count-only evidence만 기록한다.
- 실제 운영에서는 Slack/PagerDuty/Jira incident ticket과 연결할 수 있지만, 이번 Phase에서는 Markdown postmortem evidence로 제한한다.
- CI에서는 Redis stop/start incident drill을 직접 실행하지 않고 `MODE=validate-report`로 script/report 형식을 검증한다. 실제 incident evidence는 로컬 `make ops7-demo` 결과로 남긴다.
- 현재 repo에는 `infra/loki`, `infra/promtail` 구성이 없으므로 trace/log query evidence는 후속 Phase에서 보강한다.

## Troubleshooting

- Drill 실패 시 cleanup trap이 Redis를 다시 start한다. 그래도 readiness가 회복되지 않으면 `make ops7-up` 후 `make ops7-check`를 다시 실행한다.
- Duplicate smoke status가 2xx가 아니면 API health, HMAC header 설정, PostgreSQL readiness를 먼저 확인한다.
- Duplicate ledger count 또는 idempotency violation count가 0이 아니면 PostgreSQL unique constraint와 idempotency transaction 경계를 우선 점검한다.
- CI report 검증은 `MODE=validate-report`와 curated local evidence report를 대상으로 한다. CI에서 Redis stop/start를 강제하지 않는 것은 runner flakiness를 줄이기 위한 trade-off다.

## README에 기록할 문장

Ops Phase 7에서는 Redis degraded incident를 재현하고, 장애 발생부터 탐지, 영향 확인, 복구, 정합성 검증, 재발 방지 Action Item까지 `reports/ops/ops7-incident-timeline-postmortem.md`에 postmortem evidence로 남긴다.
