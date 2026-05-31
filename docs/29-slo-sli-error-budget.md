# SLO, SLI, Error Budget

> 이 문서는 Ops Phase 8 Incident Runbook을 보완하기 위한 supporting document입니다.
> 별도의 추가 Ops Phase가 아닙니다.

## 1. 목적

성능 metric은 수집만으로 충분하지 않다.
어느 수준부터 장애인지 판단할 기준이 필요하다.

이 문서는 금융 이벤트 처리 시스템의 SLI, SLO, error budget 정책을 정의한다.

## 2. SLI/SLO

| SLI | 목표 SLO | 장애 판단 |
|---|---|---|
| API 성공률 | 99.5% 이상 | 5분간 5xx > 1% |
| 이벤트 처리 p95 | 300ms 이하 | 5분간 p95 > 500ms |
| 이벤트 처리 p99 | 1s 이하 | 5분간 p99 > 2s |
| 정합성 위반 | 0건 | 1건이라도 Critical |
| Redis fallback | 허용 | 급증 시 Warning |
| DB connection 사용률 | 80% 미만 | 90% 이상 Critical |
| Backup restore 검증 | 100% 성공 | 실패 시 Critical |

## 3. 정합성 SLO

금융 정합성 위반은 error budget을 허용하지 않는다.

- ledger 중복 반영: 0건
- account balance 불일치: 0건
- 잘못된 terminal status 전이: 0건
- orphan idempotency record: 0건

정합성 위반은 성능 저하와 달리 error budget을 두지 않는다.
1건 발생 시 Critical incident로 분류한다.

## 4. Severity Level

| 장애 | Severity | 이유 |
|---|---|---|
| Ledger 중복 반영 | SEV1 | 금융 정합성 위반 |
| PostgreSQL down | SEV1 | 거래 처리 불가 |
| Secret leak | SEV1 | 이벤트 위조 가능성 |
| Redis down | SEV2 | degraded 가능, 최종 정합성 유지 |
| Nginx 5xx spike | SEV2 | 사용자 요청 실패 |
| p99 latency spike | SEV2 | timeout/retry 증가 가능 |
| Disk 85% | SEV3 | 예방 대응 가능 |
| Dashboard 일부 누락 | SEV3 | 장애 탐지 능력 저하 |

## 5. Error Budget 정책

- API latency와 5xx는 error budget을 둘 수 있다.
- Redis fallback은 정합성이 유지되는 한 Warning으로 시작한다.
- 정합성 위반, secret leak, PostgreSQL write 불가는 error budget을 두지 않는다.
- SEV1은 즉시 incident report와 재발 방지 action item을 요구한다.

## 6. Runbook Mapping

아래 표는 SLO/SLI signal을 Ops Phase 8 Incident Runbook의 장애 시나리오로 연결한다.
실제 metric이 아직 exporter 또는 application metric으로 확정되지 않은 항목은 `example metric`으로 표시한다.

| Signal | Threshold Example | Related Runbook | Evidence | Notes |
| --- | --- | --- | --- | --- |
| `financial_http_requests_total` 또는 `financial_http_errors_total` | 5분간 5xx rate 증가 | Nginx 5xx Spike / Failed Deployment | Grafana HTTP error panel, Nginx access logs | actual threshold should be adjusted after k6 baseline |
| `financial_http_request_duration_seconds` | p95 > 500ms 또는 p99 > 2s | High Latency / p95, p99 Latency Spike | Grafana latency panel, Prometheus query | compare with baseline |
| `financial_redis_fallback_total` | fallback 급증 또는 지속 증가 | Redis Down / Redis Degraded | fallback metric, structured logs, Ops5/Ops7 reports | Redis 장애 또는 지연 가능성 |
| `financial_readiness_dependency_status{dependency="postgres"}` | 0 또는 readiness FAIL | PostgreSQL Connection Exhausted | `/ready` result, DB panel, app logs | Source of Truth 접근 실패 |
| `db_connection_usage` (`example metric`) | connection usage >= 90% | PostgreSQL Connection Exhausted | DB connection panel, PostgreSQL logs | pool exhaustion 확인 |
| `financial_reconciliation_failures_total` | 최근 window에서 1건 이상 | Consistency Violation | DB query, app logs, report | 금융 정합성 위반은 1건도 심각 |
| `financial_invalid_state_transition_total` | 1건 이상 | Consistency Violation | app logs, metric panel | 상태 전이 규칙 위반 |
| security log event / secret scan result | secret, token, raw account_no 노출 의심 | Secret Leak / Security Incident | security checklist, masked logs, `make security-log-check` | 민감정보 노출 여부 확인 |

정합성 관련 signal은 availability error budget과 분리한다.
`financial_reconciliation_failures_total` 또는 invalid state transition이 1건이라도 발생하면 SEV1로 분류하고, [26-incident-runbook-index.md](26-incident-runbook-index.md)의 Consistency Violation 시나리오를 따른다.
