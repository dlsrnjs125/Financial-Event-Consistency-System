# Ops Phase 7 - Incident Timeline & Postmortem Drill

## 왜 Postmortem Drill이 필요한가

Ops Phase 5가 장애 주입과 복구 절차를 검증했다면, Ops Phase 7은 장애 대응 과정을
운영자가 추적 가능한 timeline과 postmortem evidence로 남기는 단계다.

장애 대응은 "복구됨"이라는 결과만으로 충분하지 않다. 언제 시작되었고, 언제
탐지되었으며, 어떤 영향이 있었고, 어떤 검증으로 복구를 선언했는지 남아야 다음
incident에서 더 빠르게 움직일 수 있다.

## 이번 Phase의 Incident Scenario

| 항목 | 내용 |
|---|---|
| Scenario | Redis degraded duplicate event handling |
| Severity | warning |
| 장애 주입 | Docker Compose Redis container stop |
| 핵심 기준 | PostgreSQL 기준 중복 ledger 0건, idempotency violation 0건 |
| Report | `reports/ops/ops7-incident-timeline-postmortem.md` |

Redis는 cache/lock/idempotency 보조 계층이다. Redis degraded는 즉시 Source of Truth
장애가 아니므로 warning으로 분류한다. 핵심은 PostgreSQL 기준 최종 정합성이 유지되는지
확인하는 것이다.

## Incident Timeline 설계

Timeline은 최소 다음 phase를 포함한다.

| Phase | 의미 | Evidence |
|---|---|---|
| STARTED | controlled incident drill 시작 | incident_id |
| DETECTED | Redis degraded 탐지 | readiness=degraded |
| IMPACT_CHECK | duplicate smoke 요청 실행 | first/second HTTP status |
| MITIGATED | Redis restart 요청 | container=start |
| RECOVERED | readiness 회복 | ready=PASS |
| VERIFIED | consistency 검증 완료 | duplicate_ledger_count=0 |

장애 발생 시각과 탐지 시각은 분리해 기록한다.

| 지표 | 의미 |
|---|---|
| Detection latency seconds | started -> detected |
| Mitigation latency seconds | detected -> mitigated |
| Recovery duration seconds | mitigated -> recovered |
| Total incident duration seconds | started -> recovered |

## Impact Evidence 기준

Impact evidence는 row data가 아니라 count-only 값으로 남긴다.

| 항목 | 기준 |
|---|---|
| Redis degraded detected | `/ready` Redis check가 degraded |
| API fallback behavior | Redis down 중 duplicate smoke가 2xx이고 event/ledger/idempotency count가 1 |
| Duplicate ledger count | 0 |
| Idempotency violation count | 0 |
| Consistency check | 전체 consistency count가 0 |

Report에는 secret, token, account_no 원문, 거래 row data를 기록하지 않는다.
추적성을 위해 synthetic external event id와 idempotency key는 prefix만 기록한다.

## Root Cause Analysis 기준

이번 drill의 immediate cause는 controlled Redis container stop이다. Root cause category는
`Dependency degraded`로 기록한다.

실제 운영 incident에서는 trace_id, request_id, event_id, deployment version, alert name,
operator action을 함께 연결해야 한다. 이번 Phase에서는 raw event row를 report에 남기지
않고, incident_id와 count-only evidence 중심으로 정리한다.

## Recovery Verification 기준

복구 완료는 Redis container가 start된 시점이 아니라 다음 기준을 만족한 시점이다.

- `/health` PASS
- `/ready` PASS
- recovery smoke PASS
- consistency check PASS
- duplicate ledger count 0
- idempotency violation count 0

## Action Item 작성 기준

Action item은 단순 희망사항이 아니라 후속 Phase에서 검증 가능한 항목으로 적는다.

| 우선순위 | 기준 |
|---|---|
| P1 | incident workflow와 직접 연결되어 재발 대응 시간을 줄이는 항목 |
| P2 | 추적성, 자동화, 관측 evidence 품질을 높이는 항목 |
| P3 | 운영 편의나 문서 개선 항목 |

## CI에서 검증하는 것

CI에서는 Redis stop/start를 직접 실행하지 않는다. 대신 다음을 검증한다.

- `scripts/ops7_incident_timeline_drill.sh` 문법과 실행 권한
- `MODE=help` 실행 가능 여부
- `MODE=validate-report`를 통한 script 기반 report 검증
- postmortem report 파일 존재
- 필수 section 존재
- `Overall result | PASS`
- `Duplicate ledger count | 0`
- `Idempotency violation count | 0`
- `Incident Timeline`
- `Action Items`
- duration evidence 문구

이 선택은 container stop/start로 인한 runner flakiness를 줄이기 위한 trade-off다.

## 로컬에서 검증하는 것

```bash
make ops7-up
make ops7-check
make ops7-drill
make ops7-demo
```

로컬 `make ops7-demo`는 실제 Redis container stop/start를 수행하고, duplicate smoke,
readiness recovery, consistency check까지 실행한 뒤 report를 생성한다.

## 운영상 한계와 보완 전략

- 실제 Slack/PagerDuty/Jira incident ticket 생성은 이번 Phase에서 제외한다.
- 현재 repo에는 `infra/loki`, `infra/promtail` 구성이 없으므로 log query evidence는
  Markdown postmortem으로 대체한다.
- trace_id/request_id/event_id를 완전한 분산 추적으로 연결하려면 후속 Phase에서
  OpenTelemetry 또는 Loki query evidence가 필요하다.
- Redis degraded는 warning incident로 분류하지만, fallback 증가가 DB 부하로 전이되면
  severity 재평가가 필요하다.

## Troubleshooting

- Drill 실패 시 cleanup trap이 Redis를 다시 start한다. Redis가 계속 degraded이면
  `make ops7-up` 후 `make ops7-check`를 다시 실행한다.
- Duplicate smoke가 실패하면 HMAC 설정, API health, PostgreSQL readiness를 먼저 확인한다.
- Duplicate ledger count가 0이 아니면 PostgreSQL unique constraint와 idempotency
  transaction boundary를 우선 점검한다.
- CI는 `MODE=validate-report`로 local evidence report를 검증한다. CI에서 실제 incident
  drill을 실행하지 않는 것은 구현 누락이 아니라 안정적인 gate를 위한 분리다.
