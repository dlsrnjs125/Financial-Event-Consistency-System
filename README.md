# Financial Event Consistency System

> 외부 금융 거래 이벤트의 중복 요청, 재시도, 순서 꼬임, 장애 상황에서도 거래 결과가 한 번만 정확하게 반영되는지 검증한 백엔드/DevOps 프로젝트

[![CI](https://github.com/dlsrnjs125/Financial-Event-Consistency-System/actions/workflows/ci.yml/badge.svg)](https://github.com/dlsrnjs125/Financial-Event-Consistency-System/actions)

## 1. 문제 정의

금융 이벤트 시스템에서는 외부 은행, 결제, 증권 시스템의 재시도와 timeout 때문에 동일 이벤트가 여러 번 도착할 수 있다.
이때 단순히 API가 200을 반환하는 것보다 중요한 것은 중복 원장 반영을 막고, 장애 이후에도 PostgreSQL 기준 최종 정합성을 유지하는 것이다.

이 프로젝트는 FastAPI, PostgreSQL, Redis, Prometheus/Grafana, k6, GitHub Actions, Docker Compose를 사용해 중복 처리와 장애 복구 가능성을 재현 가능한 evidence로 남겼다.

## 2. 핵심 검증 질문

| 검증 질문 | 검증 방법 | 결과 요약 |
| --- | --- | --- |
| 동일 이벤트가 여러 번 들어와도 한 번만 반영되는가? | Idempotency Key, PostgreSQL unique constraint, duplicate storm test | 중복 ledger 0건을 목표로 검증 |
| Redis 장애가 발생해도 정합성이 유지되는가? | Redis down/degraded drill, fallback, DB retry | PostgreSQL 기준 정합성 유지 |
| 잘못된 상태 전이를 막을 수 있는가? | State machine test, invalid transition metric | invalid transition 차단 |
| 배포 전후 정합성을 검증할 수 있는가? | CI/CD Gate, deploy smoke, deploy verify | 배포 Gate에서 검증 |
| 장애를 탐지하고 복구 기준을 설명할 수 있는가? | Prometheus/Grafana, Alert Rule, Incident Runbook | Ops Phase 8 Runbook으로 정리 |

## 3. 구현 범위

- FastAPI 기반 금융 이벤트 수신 API
- Idempotency Key 기반 중복 요청 처리
- PostgreSQL transaction과 unique constraint 기반 최종 정합성 보장
- Redis lock/cache 및 장애 시 degraded fallback
- 상태 머신 기반 이벤트 상태 전이 검증
- k6 기반 duplicate storm 성능 테스트
- Prometheus/Grafana 기반 관측성
- GitHub Actions 기반 CI/CD Gate
- Blue-Green 배포와 rollback 시뮬레이션
- PostgreSQL Backup/Restore DR Drill
- Incident Runbook과 postmortem 문서화

## 4. Project Scope

| Track | Scope | Status | Evidence |
| --- | --- | --- | --- |
| Development Track | Phase 1~12 | Done | consistency, idempotency, Redis fallback, k6, CI/CD, Blue-Green |
| Ops Extension Track | Phase 1~8 | Done | monitoring, DR drill, security, incident runbook |
| Supporting Docs | docs/27~34 | Supporting | threat model, SLO/SLI, evidence template, capacity appendix |
| Production Hardening Track | PH Phase 0~11 | In Progress | PH1 write suspend implementation, PostgreSQL failure policy, incident diagnosis, recovery case, AI-safe governance, latency attribution drill |

Ops Extension Track은 Phase 8 Incident Runbook에서 종료한다.
추가 문서는 새로운 Phase가 아니라 운영 판단과 포트폴리오 증거를 보완하기 위한 supporting documents로 관리한다.

Ops Phase 8에서는 장애 대응 Runbook을 최종 정리하고, Grafana p95/p99 지표와 rollback smoke/consistency gate 결과를 evidence로 남겼다.

Production Hardening Track은 기존 구현 위에 PostgreSQL 자체 장애, failover 중 미확정 거래, stale PROCESSING, 자동 incident diagnosis, recovery case 승인 흐름, AI-safe 데이터 보호 기준, latency attribution drill을 보완하는 후속 트랙이다.
PH1에서는 PostgreSQL write path가 불가능할 때 신규 금융 write를 `503` + `Retry-After`로 fail-closed 처리하는 runtime write suspend와 DB-down drill을 구현했다.
PH2에서는 PostgreSQL 장애 중 DB에 의존하지 않는 incident artifact bundle과 sanitized report skeleton을 추가했다.
PH3에서는 PH2 incident artifact를 기반으로 deterministic rule-based incident analyzer MVP를 추가했다.
PH4에서는 PH3 analyzer 결과를 recovery case로 등록하고 account quarantine write guard와 수동 승인 전 실행 차단을 추가했다.
Recovery/quarantine read-only API는 운영 민감 정보 보호를 위해 기본 비활성화하고, 내부/admin 환경에서만 opt-in으로 노출한다.
PH5에서는 stale PROCESSING detector와 count-only reconciliation job을 추가하고, 불일치 후보를 recovery case로 연결하는 기반을 구현했다.
PH6에서는 incident/recovery/reconciliation evidence를 AI나 외부 분석 도구에 전달하기 전 allowlist 기반 AI-safe context로 변환하는 sanitizer를 추가했다.
상세 설계와 구현 기록은 README가 아니라 `docs/35-*` ~ `docs/48-*` 문서에서 관리한다.

## 5. Final Verification Summary

| 검증 항목 | 방법 | 결과 요약 | 근거 문서 |
| --- | --- | --- | --- |
| 중복 이벤트 방지 | Idempotency Key + unique constraint + duplicate storm | duplicate ledger 0건 목표 검증 | [Consistency Rules](docs/03-consistency-rules.md), [Data Model](docs/12-data-model-spec.md), [Blog 03](blog/03-idempotency-key-design.md), [Blog 04](blog/04-postgresql-transaction-unique-constraint.md) |
| Redis 장애 대응 | Redis down/degraded drill + fallback | PostgreSQL 기준 정합성 유지 | [Failure Recovery Drill](docs/23-failure-recovery-runbook-drill.md), [Blog 05](blog/05-redis-lock-cache-fallback.md), [Blog 20](blog/20-failure-recovery-runbook-drill.md) |
| 상태 전이 검증 | State machine test | invalid transition 차단 | [State Transition Table](docs/13-state-transition-table.md), [Blog 06](blog/06-state-transition-test-strategy.md) |
| 성능 측정 | k6 load/stress/duplicate storm | p95/p99, 5xx, retry 지표 측정 구조 수립 | [Performance Design](docs/16-performance-measurement-design.md), [Blog 07](blog/07-k6-duplicate-storm-performance-test.md) |
| 배포 복구 | Blue-Green rollback + smoke + consistency gate | rollback 후 health/ready/smoke와 중복 ledger/event 0건 확인 | [Deployment Strategy](docs/09-deployment-strategy.md), [Phase 12](docs/phase-12-blue-green-rollback.md), [Blog 11](blog/11-blue-green-rollback-simulation.md) |
| DR Drill | PostgreSQL dump restore + consistency SQL | restore 후 정합성 검증 | [PostgreSQL DR Drill](docs/22-postgres-backup-restore-drill.md), [DR Report](reports/dr/ops4-postgres-restore-drill.md), [Blog 15](blog/15-postgresql-backup-restore-drill.md) |
| 장애 대응 | Incident Runbook + Grafana evidence + rollback verification | 장애별 탐지/대응/복구 기준 문서화 | [Incident Runbook](docs/26-incident-runbook-index.md), [SLO/SLI](docs/29-slo-sli-error-budget.md), [Blog 19](blog/19-incident-runbook-oncall-simulation.md), [Blog 22](blog/22-incident-timeline-postmortem-drill.md) |

## 6. Architecture

```text
External Financial Systems
        |
        v
      Nginx  ---- Blue/Green upstream switching
        |
        v
   FastAPI API
    |    |    |
    |    |    +-- Prometheus / Grafana
    |    +------- Redis lock/cache/fallback
    +------------ PostgreSQL Source of Truth
```

PostgreSQL은 최종 Source of Truth다.
Redis는 성능 최적화와 duplicate request 완화를 위한 보조 계층이며, Redis 장애가 발생해도 최종 정합성은 PostgreSQL transaction과 unique constraint로 검증한다.
PostgreSQL write path가 불가능한 순간에는 신규 금융 거래를 성공으로 응답하지 않고, `503 Service Unavailable`과 `Retry-After`로 동일 Idempotency-Key 재시도를 유도한다.

## 7. Quick Start

```bash
cp .env.example .env
make local-check
make local-bg
make health
make ready
```

자세한 명령은 `make help`를 사용한다.
운영 drill은 Docker Compose stack을 사용하므로 로컬 Docker daemon이 필요하다.

## 8. Key Commands

```bash
make test
make final-check
make k6-verify
make deploy-smoke
make deploy-rollback
make ops4-demo
make ops5-demo
make ops6-demo
make ops7-demo
make ph1-db-down-drill
make ph2-incident-artifact
make ph2-incident-artifact-validate
make ph3-incident-analyze
make ph3-incident-analyze-validate
make ph4-recovery-case-from-latest
make ph4-recovery-cases
make ph4-quarantines
make ph5-reconciliation-run
make ph5-reconciliation-validate
make ph6-ai-context-demo
make ph6-ai-context-validate
make ph1-write-suspend-status
make ph1-write-suspend-resume
```

## 9. 주요 문서

| 문서 | 설명 |
| --- | --- |
| [docs/01-problem-definition.md](docs/01-problem-definition.md) | 문제 정의 |
| [docs/03-consistency-rules.md](docs/03-consistency-rules.md) | 정합성 규칙 |
| [docs/04-development-roadmap.md](docs/04-development-roadmap.md) | 개발/운영 Phase 요약 |
| [docs/12-data-model-spec.md](docs/12-data-model-spec.md) | 데이터 모델 |
| [docs/15-api-contract.md](docs/15-api-contract.md) | API 계약 |
| [docs/16-performance-measurement-design.md](docs/16-performance-measurement-design.md) | 성능 측정 설계 |
| [docs/19-infra-operations-extension.md](docs/19-infra-operations-extension.md) | Ops 확장 요약 |
| [docs/26-incident-runbook-index.md](docs/26-incident-runbook-index.md) | Incident Runbook |
| [docs/29-slo-sli-error-budget.md](docs/29-slo-sli-error-budget.md) | SLO/SLI와 장애 판단 기준 |
| [docs/33-observability-evidence-plan.md](docs/33-observability-evidence-plan.md) | 증거 수집 계획 |
| [docs/35-production-hardening-roadmap.md](docs/35-production-hardening-roadmap.md) | Production Hardening 후속 보완 로드맵 |
| [docs/36-postgres-failure-and-write-suspend-policy.md](docs/36-postgres-failure-and-write-suspend-policy.md) | PostgreSQL 장애와 write suspend 정책 |
| [docs/37-incident-diagnosis-automation-design.md](docs/37-incident-diagnosis-automation-design.md) | 장애 자동 진단 설계 |
| [docs/38-recovery-case-quarantine-and-reconciliation-design.md](docs/38-recovery-case-quarantine-and-reconciliation-design.md) | Recovery case와 quarantine/reconciliation 설계 |
| [docs/39-sensitive-data-ai-governance-and-encryption-tradeoff.md](docs/39-sensitive-data-ai-governance-and-encryption-tradeoff.md) | AI-safe 민감 데이터 보호와 암호화 trade-off |
| [docs/40-postgres-ha-and-queue-tradeoff-adr.md](docs/40-postgres-ha-and-queue-tradeoff-adr.md) | PostgreSQL HA와 durable queue trade-off ADR |
| [docs/41-latency-attribution-and-external-dependency-diagnosis.md](docs/41-latency-attribution-and-external-dependency-diagnosis.md) | 내부/외부 구간별 latency 원인 분리 설계 |
| [docs/42-latency-drill-test-plan.md](docs/42-latency-drill-test-plan.md) | k6 기반 latency attribution drill 테스트 계획 |
| [docs/43-ph1-write-suspend-db-down-drill.md](docs/43-ph1-write-suspend-db-down-drill.md) | PH1 write suspend 구현과 PostgreSQL down drill |
| [docs/44-ph2-incident-artifact-sanitized-report.md](docs/44-ph2-incident-artifact-sanitized-report.md) | PH2 out-of-band incident artifact와 sanitized report |
| [docs/45-ph3-incident-analyzer-mvp.md](docs/45-ph3-incident-analyzer-mvp.md) | PH3 deterministic incident analyzer MVP |
| [docs/46-ph4-recovery-case-quarantine-manual-approval.md](docs/46-ph4-recovery-case-quarantine-manual-approval.md) | PH4 recovery case, quarantine, manual approval 구현 |
| [docs/47-ph5-stale-processing-reconciliation.md](docs/47-ph5-stale-processing-reconciliation.md) | PH5 stale PROCESSING detector와 reconciliation 구현 |
| [docs/48-ph6-ai-safe-context-sanitizer.md](docs/48-ph6-ai-safe-context-sanitizer.md) | PH6 AI-safe context sanitizer 구현 |

## 10. Blog Series

이 프로젝트는 구현 과정과 운영 검증 과정을 Velog 시리즈 형태로 정리했다.

| 주제 | 글 |
| --- | --- |
| 문제 정의 | [01. 왜 금융 이벤트 정합성인가](blog/01-why-financial-event-consistency.md) |
| Idempotency | [03. Idempotency Key 설계](blog/03-idempotency-key-design.md) |
| DB 정합성 | [04. PostgreSQL Transaction과 Unique Constraint](blog/04-postgresql-transaction-unique-constraint.md) |
| Redis Fallback | [05. Redis Lock/Cache/Fallback](blog/05-redis-lock-cache-fallback.md) |
| 성능 테스트 | [07. k6 Duplicate Storm 성능 테스트](blog/07-k6-duplicate-storm-performance-test.md) |
| 배포 안정성 | [11. Blue-Green Rollback Simulation](blog/11-blue-green-rollback-simulation.md) |
| DR Drill | [15. PostgreSQL Backup/Restore DR Drill](blog/15-postgresql-backup-restore-drill.md) |
| Incident Runbook | [19. Incident Runbook & On-call Simulation](blog/19-incident-runbook-oncall-simulation.md) |
| Postmortem | [22. Incident Timeline & Postmortem Drill](blog/22-incident-timeline-postmortem-drill.md) |

## 11. 한계와 향후 고도화

이번 프로젝트의 고도화 후보는 구현 부족 목록이 아니라, 현재 프로젝트의 핵심 범위인 "정합성 보장과 운영 복구 가능성 검증" 밖에 있는 확장 항목으로 분리했다.

- 실제 운영 트래픽 기반 alert threshold 조정이 필요하다.
- Slack/PagerDuty 같은 외부 on-call 연동은 제외했다.
- Kubernetes 기반 운영 전환은 제외했다.
- Loki/OpenTelemetry 기반 trace query evidence는 향후 고도화로 남겼다.
- Capacity Planning, Change Management, Ansible, PowerShell 문서는 supporting/optional docs로 관리한다.
- Production Hardening PH1 write suspend는 단일 API 인스턴스 기준으로 구현했다.
- PH4 recovery case/quarantine은 자동 보정 실행이 아니라 수동 승인 전 실행 차단과 evidence 연결까지 구현했다.
- PH5 reconciliation은 탐지와 recovery case 연결까지만 수행하며 금전 상태를 자동 수정하지 않는다.
- PH6 AI-safe context sanitizer는 외부 AI API를 호출하지 않고 allowlist 기반 context 생성과 검증까지만 수행한다.
- PostgreSQL HA/Queue 도입, latency attribution instrumentation과 k6 latency drill은 후속 구현 후보로 남겼다.

## 12. 최종 요약

Development Track에서는 금융 이벤트 정합성 처리 시스템을 구현했고, Ops Extension Track에서는 모니터링, DR Drill, 보안 통제, 장애 대응 Runbook까지 정리했다.
Ops Phase 8 Incident Runbook을 마지막으로 운영 확장 트랙을 종료했으며, 추가 문서는 새로운 Phase가 아니라 운영 판단과 포트폴리오 evidence를 보완하는 supporting documents로 관리한다.
Production Hardening Track은 운영 확장 종료 이후의 후속 보완 트랙으로, PostgreSQL 장애 중 성공 응답 금지, 자동 진단과 수동 승인 경계, 민감 데이터의 AI-safe 처리 원칙을 문서화하고 일부 안전장치를 구현한다.
