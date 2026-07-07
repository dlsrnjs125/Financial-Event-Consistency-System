# Ops Phase 8 - Incident Runbook Finalization

> 이 문서는 Ops Phase 8의 핵심 산출물이다.
> Ops Phase 8은 본 프로젝트의 마지막 필수 Ops 단계이며, 장애 탐지·대응·복구 검증·재발 방지 절차를 정리한다.

## 1. 해결하려는 운영 문제

모니터링은 장애를 감지하는 장치이고, Runbook은 장애가 났을 때 운영자가 어떤 순서로 판단할지 고정하는 문서다.

Ops Phase 8은 Redis 장애, DB connection 고갈, Nginx 5xx, p99 latency, failed deployment, consistency violation, security incident 상황을 운영자가 추적 가능한 runbook으로 정리한다.
새 장애 주입 기능을 늘리는 단계가 아니라, Ops Phase 4~7에서 만든 DR Drill, Failure Recovery Drill, Alert Rule, Postmortem evidence를 한 곳에서 찾을 수 있게 연결하는 문서화 단계다.

## 2. 구현 범위

- 장애별 runbook 작성
- alert rule과 runbook 링크 연결
- 장애 훈련 명령, local evidence, manual checklist 연결
- 복구 후 정합성 검증 기준 정리
- incident report 결과 파일 설계
- SLO/SLI, observability evidence, measurement result template 연결

## 3. 제외 범위

- 실제 on-call rotation 시스템 구축은 제외한다.
- PagerDuty, Opsgenie 같은 외부 incident tool 연동은 제외한다.
- 장애 자동 복구는 초기 범위에서 제외한다.
- 운영 DB destructive drill은 제외한다.

## 4. Ops Phase 8 Completion Criteria

Ops Phase 8은 Incident Runbook을 완성하고, 장애 대응 기준을 문서화하는 단계다.

완료 기준:

- 필수 장애 시나리오별 Runbook이 존재한다.
- 각 Runbook은 장애 상황, 예상 원인, 사용자 영향, 탐지 방법, 대응 방법, 복구 검증, 재발 방지, README/블로그 기록 문장을 포함한다.
- 각 Runbook은 관련 SLO/SLI와 연결된다.
- 각 Runbook은 수집해야 할 관측 증거와 연결된다.
- 실제 존재하는 명령과 수동 확인 항목이 구분되어 있다.
- 실제 측정하지 않은 결과는 placeholder 또는 planned verification으로 표시되어 있다.
- Ops Extension Track은 Phase 8에서 종료된다.

## 5. Supporting Documents 연결

| Supporting document | Runbook에서 사용하는 역할 |
| --- | --- |
| [29-slo-sli-error-budget.md](29-slo-sli-error-budget.md) | 장애 심각도, SLO 위반, error budget 판단 기준 |
| [33-observability-evidence-plan.md](33-observability-evidence-plan.md) | Prometheus/Grafana/log screenshot evidence 수집 기준 |
| [34-measurement-result-template.md](34-measurement-result-template.md) | 장애 대응 결과와 측정값 기록 양식 |
| [51-ph9-production-hardening-drill-plan.md](51-ph9-production-hardening-drill-plan.md) | PH1~PH8 production hardening drill catalog와 evidence runner 기준 |
| [27-threat-model.md](27-threat-model.md) | 보안성 장애 시나리오의 위협 근거 |
| [32-security-checklist.md](32-security-checklist.md) | 운영 보안 점검 기준 |

## 6. 파일/디렉터리 기준

```text
docs/
  runbooks/
    redis-down.md
    postgres-connection-exhausted.md
    nginx-5xx-spike.md
    high-latency-p99.md
    disk-full.md
    failed-deployment.md
    consistency-violation.md
    secret-leak.md
    backup-restore-failed.md
    metrics-unavailable.md

reports/
  incidents/
    redis-down/
      result.md
    failed-deployment/
      result.md
```

## 7. 검증 기준

| Scenario | Verification mode | Evidence |
| --- | --- | --- |
| Redis Down / Redis Degraded | Local command | `make ops5-demo`, `make ops7-demo` |
| PostgreSQL connection exhausted | Manual checklist / planned verification | readiness failure, DB connection metric, recovery checklist |
| Nginx 5xx spike | Manual checklist / planned verification | Nginx access log, HTTP 5xx metric, routed smoke |
| High latency / p99 latency spike | Local report / manual checklist | k6 result, latency dashboard, p95/p99 metric |
| Failed deployment / rollback | Local command | `make ops2-demo`, `make deploy-rollback` |
| Consistency violation | Local consistency check | duplicate ledger count, idempotency violation count, reconciliation failure metric |
| Secret leak or security incident | Manual checklist | Threat Model, Secret Management Policy, Security Checklist |

### 실제 존재하는 검증 명령

아래 명령은 현재 Makefile에 존재하는 명령만 기록한다.
자동화되지 않은 항목은 code block에 넣지 않고 Manual verification 또는 Planned automation으로 분리한다.

```bash
make ops2-demo
make ops4-demo
make ops5-demo
make ops6-demo
make ops7-demo
make local-status
make failure-status
make deploy-status
make deploy-smoke
make deploy-rollback
make deploy-verify
make k6-normal
make k6-peak
make k6-duplicate
make k6-verify
make security-log-check
```

Manual verification:

- Grafana dashboard에서 p95/p99 latency, 5xx, Redis fallback, DB connection panel을 확인한다.
- structured log에서 `trace_id`, `request_id`, `event_id`, `error_code` 기준으로 장애 요청을 추적한다.
- PostgreSQL connection exhaustion은 DB exporter panel, PostgreSQL log, `/ready` failure를 기준으로 확인한다.
- Secret Leak / Security Incident는 Threat Model, Secret Management Policy, Security Checklist와 `make security-log-check` 결과를 함께 확인한다.

Planned automation:

- `make ops8-incident-drill`은 현재 존재하지 않는다. 필요하면 후속 고도화에서 추가한다.
- DB connection exhaustion, Nginx 5xx spike, Secret leak drill은 현재 Runbook/manual checklist 기준으로 관리한다.
- PH9의 [production hardening drill plan](51-ph9-production-hardening-drill-plan.md)은 PH1~PH8 hardening drill을 안전한 catalog/report로 묶고, 실제 장애 주입 또는 승인 작업은 manual boundary로 분리한다.

성공 기준:

- 각 장애별 local evidence 또는 manual checklist 존재
- 장애 재현 또는 planned verification 기준 명시
- alert firing 또는 detection metric 확인 기준 명시
- runbook 절차대로 복구 가능
- 복구 후 정합성 검증 통과
- incident report 또는 measurement result template으로 결과 기록 가능

## 8. 완료 기준과 README에 남길 결과

### Runbook 목록

| 장애 | 문서 |
|---|---|
| Redis Down | [runbooks/redis-down.md](runbooks/redis-down.md) |
| Redis Degraded | [23-failure-recovery-runbook-drill.md](23-failure-recovery-runbook-drill.md), [25-incident-timeline-postmortem-drill.md](25-incident-timeline-postmortem-drill.md) |
| PostgreSQL Connection Exhausted | [runbooks/postgres-connection-exhausted.md](runbooks/postgres-connection-exhausted.md) |
| Nginx 5xx Spike | [runbooks/nginx-5xx-spike.md](runbooks/nginx-5xx-spike.md) |
| High Latency p99 | [runbooks/high-latency-p99.md](runbooks/high-latency-p99.md) |
| Disk Full | [runbooks/disk-full.md](runbooks/disk-full.md) |
| Failed Deployment | [runbooks/failed-deployment.md](runbooks/failed-deployment.md) |
| Consistency Violation | [runbooks/consistency-violation.md](runbooks/consistency-violation.md) |
| Secret Leak | [runbooks/secret-leak.md](runbooks/secret-leak.md) |
| Backup Restore Failed | [runbooks/backup-restore-failed.md](runbooks/backup-restore-failed.md) |
| Metrics Unavailable | [runbooks/metrics-unavailable.md](runbooks/metrics-unavailable.md) |

## 9. Runbook Index

`docs/26-incident-runbook-index.md`는 Phase 8의 index, completion criteria, SLO/SLI mapping을 담당한다.
실제 장애 대응 절차의 canonical source는 `docs/runbooks/*.md` 파일이다.
절차를 수정할 때는 아래 개별 Runbook을 우선 수정하고, 이 문서는 링크와 요약만 갱신한다.

| Scenario | Severity | Primary Signal | Canonical Runbook | Evidence |
| --- | --- | --- | --- | --- |
| Redis Down / Redis Degraded | SEV2 | `redis_up`, Redis fallback, readiness degraded | [runbooks/redis-down.md](runbooks/redis-down.md) | Ops5/Ops7 reports, Grafana Redis/API panels |
| PostgreSQL Connection Exhausted | SEV1 | readiness postgres fail, DB connection usage | [runbooks/postgres-connection-exhausted.md](runbooks/postgres-connection-exhausted.md) | DB connection panel, `/ready`, consistency SQL |
| Nginx 5xx Spike | SEV2 | 5xx rate, upstream status | [runbooks/nginx-5xx-spike.md](runbooks/nginx-5xx-spike.md) | Nginx access log, `make deploy-smoke` |
| High Latency / p95, p99 Latency Spike | SEV2 | p95/p99 latency, request duration histogram | [runbooks/high-latency-p99.md](runbooks/high-latency-p99.md) | k6 report, Grafana latency panel |
| Failed Deployment / Rollback | SEV2 | failed smoke, active upstream mismatch | [runbooks/failed-deployment.md](runbooks/failed-deployment.md) | `make deploy-status`, `make deploy-rollback`, `make deploy-verify` |
| Consistency Violation | SEV1 | duplicate ledger, reconciliation failure, invalid transition | [runbooks/consistency-violation.md](runbooks/consistency-violation.md) | count-only SQL, Ops4/Ops5/Ops7 reports |
| Secret Leak / Security Incident | SEV1 | secret scan, masked log failure, endpoint exposure | [runbooks/secret-leak.md](runbooks/secret-leak.md) | `make security-log-check`, security checklist |

Additional supporting Runbooks:

| Scenario | Canonical Runbook | Role |
| --- | --- | --- |
| Disk Full | [runbooks/disk-full.md](runbooks/disk-full.md) | Optional infra incident appendix |
| Backup Restore Failed | [runbooks/backup-restore-failed.md](runbooks/backup-restore-failed.md) | Ops4 DR troubleshooting appendix |
| Metrics Unavailable | [runbooks/metrics-unavailable.md](runbooks/metrics-unavailable.md) | Ops1/Ops6 observability troubleshooting appendix |

## Evidence

| Evidence | Image |
| --- | --- |
| Ops Phase 8 Runbook Index | `docs/images/ops8-01-incident-runbook-index.png` |
| Grafana Request/Latency Overview | `docs/images/ops8-02-grafana-request-latency-overview.png` |
| Rollback Smoke and Consistency PASS | `docs/images/ops8-03-rollback-smoke-consistency-pass.png` |

## 공통 템플릿

각 runbook은 아래 구조를 따른다.

1. 장애 상황
2. 예상 원인
3. 사용자 영향
4. 탐지 방법
5. 대응 방법
6. 복구 검증
7. 재발 방지
8. README/블로그 기록 문장
9. 사후 기록 템플릿

## Alert Rule 연결

각 Alert Rule에는 반드시 runbook 링크를 추가한다.

```yaml
annotations:
  runbook: "docs/runbooks/redis-down.md"
```

## Severity Level

| Severity | 기준 | 예시 |
|---|---|---|
| SEV1 | 금융 정합성 위반 또는 핵심 거래 처리 불가 | ledger 중복 반영, PostgreSQL down, secret leak |
| SEV2 | degraded mode 지속 또는 사용자 요청 실패 증가 | Redis down, Nginx 5xx spike, p99 급증 |
| SEV3 | 예방 대응 가능한 운영 위험 | disk 85%, backup 지연, dashboard 일부 누락 |
| SEV4 | 비긴급 개선 항목 | 문서 보완, alert threshold 조정 |

정합성 위반은 성능 저하와 다르게 error budget을 두지 않는다.
1건 발생 시 SEV1 incident로 분류한다.

## Incident Lifecycle

Runbook은 다음 lifecycle을 기준으로 작성한다.

1. Preparation
   - dashboard, alert, runbook, backup 준비
2. Detection & Analysis
   - alert firing, dashboard 확인, 영향 범위 판단
3. Containment
   - rate limit 강화, traffic rollback, admin endpoint 제한, degraded mode 유지
4. Eradication & Recovery
   - 원인 제거, 서비스 복구, 정합성 검증
5. Post-Incident Activity
   - incident report, 재발 방지 action item, threshold/runbook 수정
