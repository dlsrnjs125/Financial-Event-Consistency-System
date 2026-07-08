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
| Production Hardening Track | PH Phase 0~11 | Local Evidence Complete | PostgreSQL failure policy, incident diagnosis, recovery case, AI-safe governance, HMAC rotation, HA/Queue ADR, latency attribution/drill evidence |

Ops Extension Track은 Phase 8 Incident Runbook에서 종료한다.
추가 문서는 새로운 Phase가 아니라 운영 판단과 포트폴리오 증거를 보완하기 위한 supporting documents로 관리한다.

Ops Phase 8에서는 장애 대응 Runbook을 최종 정리하고, Grafana p95/p99 지표와 rollback smoke/consistency gate 결과를 evidence로 남겼다.

Production Hardening Track은 기존 정합성 구현 위에 PostgreSQL 장애, incident artifact, recovery case, stale reconciliation, AI-safe context, HMAC rotation, HA/Queue ADR, latency attribution, latency drill evidence runner를 추가한 후속 검증 트랙이다.

이 트랙은 production-ready 완성 선언이 아니라, local Docker Compose와 sample evidence 기준으로 운영 장애를 어떻게 정의하고 검증했는지 보여주는 포트폴리오 evidence track이다.
상세 설계와 구현 기록은 README가 아니라 `docs/35-*` ~ `docs/53-*` 문서에서 관리한다.

## 5. 대표 트러블슈팅

1. PostgreSQL 장애 중 성공 응답 금지
   - DB write path가 불가능할 때 신규 금융 write를 `200 OK`로 처리하지 않고 `503 + Retry-After`로 fail-closed 처리했다.

2. Stale PROCESSING 자동 보정 금지
   - 처리 중 멈춘 이벤트를 자동 완료/실패 처리하지 않고 count-only reconciliation과 recovery case로 연결했다.

3. AI-safe Incident Context
   - incident/recovery/reconciliation evidence를 AI에 넘기기 전에 allowlist 기반 sanitizer로 민감 데이터를 제거했다.

4. Partner HMAC Rotation
   - current/previous/next/revoked/disabled secret 상태를 분리하고, 실제 write API에서는 next secret을 허용하지 않도록 했다.

5. Latency Attribution
   - k6 p95/p99만으로 DB 문제를 단정하지 않고 Nginx/FastAPI/Redis/PostgreSQL/outbound/blackbox evidence를 함께 분석했다.

## 6. Final Verification Summary

| 검증 항목 | 방법 | 결과 요약 | 근거 문서 |
| --- | --- | --- | --- |
| 중복 이벤트 방지 | Idempotency Key + unique constraint + duplicate storm | duplicate ledger 0건 목표 검증 | [Consistency Rules](docs/03-consistency-rules.md), [Data Model](docs/12-data-model-spec.md), [Blog 03](blog/03-idempotency-key-design.md), [Blog 04](blog/04-postgresql-transaction-unique-constraint.md) |
| Redis 장애 대응 | Redis down/degraded drill + fallback | PostgreSQL 기준 정합성 유지 | [Failure Recovery Drill](docs/23-failure-recovery-runbook-drill.md), [Blog 05](blog/05-redis-lock-cache-fallback.md), [Blog 20](blog/20-failure-recovery-runbook-drill.md) |
| 상태 전이 검증 | State machine test | invalid transition 차단 | [State Transition Table](docs/13-state-transition-table.md), [Blog 06](blog/06-state-transition-test-strategy.md) |
| 성능 측정 | k6 load/stress/duplicate storm | p95/p99, 5xx, retry 지표 측정 구조 수립 | [Performance Design](docs/16-performance-measurement-design.md), [Blog 07](blog/07-k6-duplicate-storm-performance-test.md) |
| 배포 복구 | Blue-Green rollback + smoke + consistency gate | rollback 후 health/ready/smoke와 중복 ledger/event 0건 확인 | [Deployment Strategy](docs/09-deployment-strategy.md), [Phase 12](docs/phase-12-blue-green-rollback.md), [Blog 11](blog/11-blue-green-rollback-simulation.md) |
| DR Drill | PostgreSQL dump restore + consistency SQL | restore 후 정합성 검증 | [PostgreSQL DR Drill](docs/22-postgres-backup-restore-drill.md), [DR Report](reports/dr/ops4-postgres-restore-drill.md), [Blog 15](blog/15-postgresql-backup-restore-drill.md) |
| 장애 대응 | Incident Runbook + Grafana evidence + rollback verification | 장애별 탐지/대응/복구 기준 문서화 | [Incident Runbook](docs/26-incident-runbook-index.md), [SLO/SLI](docs/29-slo-sli-error-budget.md), [Blog 19](blog/19-incident-runbook-oncall-simulation.md), [Blog 22](blog/22-incident-timeline-postmortem-drill.md) |

## 7. Architecture

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

## 8. Quick Start

```bash
cp .env.example .env
make local-check
make local-bg
make health
make ready
```

자세한 명령은 `make help`를 사용한다.
운영 drill은 Docker Compose stack을 사용하므로 로컬 Docker daemon이 필요하다.

## 9. Key Commands

```bash
make final-check
make k6-verify
make deploy-smoke
make ops4-demo
make ph9-hardening-drill-demo
make ph10-latency-attribution-demo
make ph11-latency-drill-demo
```

전체 개발/운영/Production Hardening 명령은 [docs/04-development-roadmap.md](docs/04-development-roadmap.md)와 [docs/35-production-hardening-roadmap.md](docs/35-production-hardening-roadmap.md)를 기준으로 확인한다.

## 10. 주요 문서

| 문서 | 설명 |
| --- | --- |
| [docs/01-problem-definition.md](docs/01-problem-definition.md) | 문제 정의 |
| [docs/03-consistency-rules.md](docs/03-consistency-rules.md) | 정합성 규칙 |
| [docs/04-development-roadmap.md](docs/04-development-roadmap.md) | 개발/운영 Phase 요약 |
| [docs/12-data-model-spec.md](docs/12-data-model-spec.md) | 데이터 모델 |
| [docs/15-api-contract.md](docs/15-api-contract.md) | API 계약 |
| [docs/26-incident-runbook-index.md](docs/26-incident-runbook-index.md) | Incident Runbook |
| [docs/29-slo-sli-error-budget.md](docs/29-slo-sli-error-budget.md) | SLO/SLI와 장애 판단 기준 |
| [docs/35-production-hardening-roadmap.md](docs/35-production-hardening-roadmap.md) | Production Hardening 후속 보완 로드맵 |
| [docs/51-ph9-production-hardening-drill-plan.md](docs/51-ph9-production-hardening-drill-plan.md) | PH9 production hardening drill catalog와 evidence runner |
| [docs/52-ph10-latency-attribution-diagnosis.md](docs/52-ph10-latency-attribution-diagnosis.md) | PH10 latency attribution analyzer와 sanitized report |
| [docs/53-ph11-latency-drill-evidence-runner.md](docs/53-ph11-latency-drill-evidence-runner.md) | PH11 latency drill safe evidence runner |

전체 문서는 `docs/` 디렉터리에서 phase별로 관리한다.

## 11. Blog Series

프로젝트 구현 과정과 운영 검증 과정은 Velog 시리즈 형태로 정리했다.
README에는 대표 글만 남기고, 전체 공개/비공개 기준은 [blog/README.md](blog/README.md)에서 관리한다.

| 주제 | 글 |
| --- | --- |
| 문제 정의 | [금융 이벤트 시스템에서 가장 무서운 장애는 500이 아니라 중복 반영이었다](blog/01-why-financial-event-consistency.md) |
| 정합성 설계 | [Redis Lock을 믿지 않고 PostgreSQL Unique Constraint를 마지막 방어선으로 둔 이유](blog/04-postgresql-transaction-unique-constraint.md) |
| 성능 검증 | [p99가 느려져도 원장이 두 번 반영되면 안 된다](blog/07-k6-duplicate-storm-performance-test.md) |
| 배포 안정성 | [배포 실패 시 DB를 되돌리지 않고 트래픽만 Blue로 되돌린 이유](blog/11-blue-green-rollback-simulation.md) |
| 장애 대응 | [장애를 복구했다는 말만으로는 부족했다](blog/19-incident-runbook-oncall-simulation.md) |
| Production Hardening | [PostgreSQL이 죽었을 때 성공 응답도, 장애 기록 유실도 막고 싶었다](blog/23-postgresql-down-write-suspend-drill.md) |

## 12. 한계와 향후 고도화

이번 프로젝트의 고도화 후보는 구현 부족 목록이 아니라, 현재 프로젝트의 핵심 범위인 "정합성 보장과 운영 복구 가능성 검증" 밖에 있는 확장 항목으로 분리했다.

- 실제 운영 트래픽 기반 alert threshold 조정이 필요하다.
- Slack/PagerDuty 같은 외부 on-call 연동과 Kubernetes 운영 전환은 제외했다.
- PostgreSQL HA, durable queue, Vault/KMS, OpenTelemetry full tracing은 후속 후보로 남겼다.
- Production Hardening drill은 local Docker Compose와 sample evidence 기준이며, destructive fault injection을 기본 실행하지 않는다.
- Recovery, write resume, 원장 보정, partner key retirement는 자동 실행이 아니라 수동 승인 경계로 남긴다.

## 13. 최종 요약

Development Track에서는 금융 이벤트 정합성 처리 시스템을 구현했고, Ops Extension Track에서는 모니터링, DR Drill, 보안 통제, 장애 대응 Runbook까지 정리했다.
Ops Phase 8 Incident Runbook을 마지막으로 운영 확장 트랙을 종료했으며, 추가 문서는 새로운 Phase가 아니라 운영 판단과 포트폴리오 evidence를 보완하는 supporting documents로 관리한다.
Production Hardening Track은 운영 확장 종료 이후의 후속 보완 트랙으로, PostgreSQL 장애 중 성공 응답 금지, 자동 진단과 수동 승인 경계, 민감 데이터의 AI-safe 처리 원칙을 문서화하고 일부 안전장치를 구현한다.
