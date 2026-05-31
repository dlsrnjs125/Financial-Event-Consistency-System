# Blog Publishing Plan

이 디렉터리는 Velog 시리즈 게시를 위한 초안 문서 모음이다.
Docs는 설계/운영 근거 문서이고, Blog는 면접관과 독자가 읽기 쉬운 서술형 글이다.

## Recommended Ops Posting Order

| Post | Source Docs | Purpose |
| --- | --- | --- |
| Ops 1. Monitoring Evidence | `docs/07-observability.md`, `docs/20-infra-metrics-design.md`, `docs/33-observability-evidence-plan.md` | Prometheus/Grafana 증거 정리 |
| Ops 2. Blue-Green & Rollback | `docs/09-deployment-strategy.md`, `docs/30-change-management.md` | 배포 안정성 |
| Ops 3. PostgreSQL DR Drill | `docs/22-postgres-backup-restore-drill.md`, `reports/dr/ops4-postgres-restore-drill.md` | 복구 가능성 검증 |
| Ops 4. Failure Simulation | `docs/08-failure-scenarios.md`, `docs/23-failure-recovery-runbook-drill.md`, `reports/ops/` | 장애 재현과 복구 검증 |
| Ops 5. Redis Degraded Postmortem | `docs/25-incident-timeline-postmortem-drill.md`, `reports/ops/ops7-incident-timeline-postmortem.md` | 장애 분석과 postmortem evidence |
| Ops 6. Internal Security | `docs/27-threat-model.md`, `docs/28-secret-management-policy.md`, `docs/32-security-checklist.md` | 운영 보안 |
| Ops 7. Incident Runbook | `docs/26-incident-runbook-index.md`, `docs/29-slo-sli-error-budget.md`, `docs/33-observability-evidence-plan.md`, `docs/34-measurement-result-template.md` | 장애 대응 체계 |
| Ops 8. Final Retrospective | `README.md`, `docs/19-infra-operations-extension.md` | 운영 확장 회고 |

## Merge Recommendations

아래 주제는 게시 시 하나의 글로 합칠 수 있다.

- Alert Rule, Incident Runbook, SLO/SLI/Error Budget, Observability Evidence Plan
- Threat Model, Secret Management, Security Checklist, Internal Network Security

아래 주제는 별도 글로 유지하는 것이 좋다.

- PostgreSQL Backup/Restore DR Drill
- Blue-Green Deployment & Rollback
- Redis Degraded Incident Postmortem
- k6 성능 테스트 결과
- Prometheus/Grafana 모니터링 증거

## Scope Note

Ops Extension Track은 Phase 8 Incident Runbook에서 종료한다.
Ansible, PowerShell, Capacity Planning, Change Management는 필수 Phase가 아니라 향후 운영 고도화 후보로 다룬다.
