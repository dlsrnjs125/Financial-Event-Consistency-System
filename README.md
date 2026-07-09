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
| 장애를 탐지하고 복구 기준을 설명할 수 있는가? | Prometheus/Grafana, Alert Rule, Incident Runbook | incident timeline과 postmortem evidence로 정리 |

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
| Core Consistency Track | 금융 이벤트 수신, idempotency, 상태 전이, PostgreSQL 정합성 | Done | duplicate storm, unique constraint, state transition test |
| Operations Evidence Track | 모니터링, Blue-Green, DR Drill, Runbook/Postmortem | Done | Grafana, rollback smoke, DR report, incident timeline |
| Production Hardening Track | DB down fail-closed, recovery case, AI-safe context, HMAC rotation, latency attribution | Local Evidence Complete | sanitized artifact, recovery case, latency drill evidence |
| Supporting Docs | docs/27~34 | Supporting | threat model, SLO/SLI, evidence template, capacity appendix |

Operations Evidence Track은 Incident Runbook 정리까지 완료된 운영 검증 흐름이다.
추가 문서는 새로운 Phase가 아니라 운영 판단과 포트폴리오 증거를 보완하기 위한 supporting documents로 관리한다.

운영 evidence에서는 장애 대응 Runbook을 정리하고, Grafana p95/p99 지표와 rollback smoke/consistency gate 결과를 evidence로 남겼다.

Production Hardening Track은 기존 정합성 구현 위에 PostgreSQL 장애, incident artifact, recovery case, stale reconciliation, AI-safe context, HMAC rotation, HA/Queue ADR, latency attribution, latency drill evidence runner를 추가한 후속 검증 트랙이다.

이 트랙은 production-ready 완성 선언이 아니라, local Docker Compose와 sample evidence 기준으로 운영 장애를 어떻게 정의하고 검증했는지 보여주는 포트폴리오 evidence track이다.
상세 설계와 구현 기록은 README가 아니라 `docs/35-*` ~ `docs/53-*` 문서에서 관리한다.

## 5. 대표 트러블슈팅

1. 같은 Idempotency-Key + 다른 body를 replay하지 않고 분리
   - 동일 key라도 request hash가 다르면 기존 성공 응답을 replay하지 않고 `409 Conflict`로 처리했다.

2. Redis 장애 시 PostgreSQL unique constraint로 duplicate ledger 방어
   - Redis down/degraded 상태에서는 성능이 떨어질 수 있지만, 최종 중복 방지는 PostgreSQL constraint와 transaction 경계로 검증했다.

3. k6 duplicate storm에서 p99보다 ledger 중복 여부를 우선 확인
   - 응답 지연보다 금융 정합성 위반이 더 치명적이므로 duplicate ledger count 0건을 핵심 기준으로 두었다.

4. Blue-Green 전환을 설정 파일이 아니라 routed identity로 확인
   - Nginx 설정 변경만 믿지 않고 실제 public route가 Blue/Green 중 어디로 향하는지 smoke evidence로 확인했다.

5. PostgreSQL DR Drill에서 restore DB + consistency SQL + checksum을 evidence 기준으로 사용
   - backup 생성 여부가 아니라 별도 restore DB 복원과 정합성 SQL 통과를 DR evidence 기준으로 삼았다.

6. PostgreSQL down 중 성공 응답과 장애 기록 유실을 함께 방지
   - 신규 write는 `503 + Retry-After`로 fail-closed 처리하고, out-of-band incident artifact와 수동 승인 경계를 분리했다.

## 6. Final Verification Summary

| 검증 항목 | 방법 | 결과 요약 | 근거 문서 |
| --- | --- | --- | --- |
| 중복 이벤트 방지 | Idempotency Key + unique constraint + duplicate storm | duplicate ledger 0건 목표 검증 | [Consistency Rules](docs/03-consistency-rules.md), [Data Model](docs/12-data-model-spec.md), [Blog 03](blog/series/03-idempotency-key-request-hash.md), [Blog 04](blog/series/04-postgres-unique-constraint-redis-fallback.md) |
| Redis 장애 대응 | Redis down/degraded drill + fallback | PostgreSQL 기준 정합성 유지 | [Failure Recovery Drill](docs/23-failure-recovery-runbook-drill.md), [Blog 04](blog/series/04-postgres-unique-constraint-redis-fallback.md), [Blog 07](blog/series/07-docker-compose-failure-dependency-policy.md) |
| 상태 전이 검증 | State machine test | invalid transition 차단 | [State Transition Table](docs/13-state-transition-table.md), [Blog 02](blog/series/02-state-machine-domain-rules.md) |
| 성능 측정 | k6 load/stress/duplicate storm | p95/p99, 5xx, retry 지표 측정 구조 수립 | [Performance Design](docs/16-performance-measurement-design.md), [Blog 05](blog/series/05-k6-duplicate-storm-ledger-consistency.md) |
| 배포 복구 | Blue-Green rollback + smoke + consistency gate | rollback 후 health/ready/smoke와 중복 ledger/event 0건 확인 | [Deployment Strategy](docs/09-deployment-strategy.md), [Phase 12](docs/phase-12-blue-green-rollback.md), [Blog 09](blog/series/09-blue-green-traffic-rollback.md) |
| DR Drill | PostgreSQL dump restore + consistency SQL | restore 후 정합성 검증 | [PostgreSQL DR Drill](docs/22-postgres-backup-restore-drill.md), [DR Report](reports/dr/ops4-postgres-restore-drill.md), [Blog 10](blog/series/10-postgres-backup-restore-drill.md) |
| 장애 대응 | Incident Runbook + Grafana evidence + rollback verification | 장애별 탐지/대응/복구 기준 문서화 | [Incident Runbook](docs/26-incident-runbook-index.md), [SLO/SLI](docs/29-slo-sli-error-budget.md), [Blog 12](blog/series/12-runbook-alert-postmortem-evidence.md) |
| PostgreSQL write suspend | DB down drill + `503`/`Retry-After` + retry contract | DB commit 근거 없는 성공 응답 금지 | [PostgreSQL Failure Policy](docs/36-postgres-failure-and-write-suspend-policy.md), [Blog 13](blog/series/13-postgres-down-write-suspend-incident-artifact.md) |
| AI-safe / HMAC boundary | sanitizer demo + HMAC rotation evidence | raw value/signature 미저장, next secret write API 미허용 | [AI-safe Context](docs/48-ph6-ai-safe-context-sanitizer.md), [Blog 15](blog/series/15-ai-safe-context-hmac-rotation-boundary.md) |
| Latency attribution | LAT-001~LAT-006 evidence runner | p99 상승을 계층별 후보로 분류, consistency counter 우선 | [Latency Attribution](docs/52-ph10-latency-attribution-diagnosis.md), [Blog 16](blog/series/16-latency-attribution-drill-evidence.md) |

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
make k6-duplicate
make k6-verify
make ops2-demo
make ops4-demo
make ops7-demo
make ph1-db-down-drill
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
| 문제 정의 | [금융 이벤트 시스템에서 가장 무서운 장애는 500이 아니라 중복 반영이었다](blog/series/01-duplicate-financial-event-problem.md) |
| 정합성 설계 | [Redis Lock을 믿지 않고 PostgreSQL Unique Constraint를 마지막 방어선으로 둔 이유](blog/series/04-postgres-unique-constraint-redis-fallback.md) |
| 성능 검증 | [p99가 느려져도 원장이 두 번 반영되면 안 된다](blog/series/05-k6-duplicate-storm-ledger-consistency.md) |
| 배포 안정성 | [배포 실패 시 DB를 되돌리지 않고 트래픽만 Blue로 되돌린 이유](blog/series/09-blue-green-traffic-rollback.md) |
| 장애 대응 | [장애를 복구했다는 말만으로는 부족했다](blog/series/12-runbook-alert-postmortem-evidence.md) |
| Production Hardening | [PostgreSQL이 죽었을 때 성공 응답도, 장애 기록 유실도 막고 싶었다](blog/series/13-postgres-down-write-suspend-incident-artifact.md) |

## 12. 한계와 향후 고도화

이번 프로젝트의 고도화 후보는 구현 부족 목록이 아니라, 현재 프로젝트의 핵심 범위인 "정합성 보장과 운영 복구 가능성 검증" 밖에 있는 확장 항목으로 분리했다.

- 실제 운영 트래픽 기반 alert threshold 조정이 필요하다.
- Slack/PagerDuty 같은 외부 on-call 연동과 Kubernetes 운영 전환은 제외했다.
- PostgreSQL HA, durable queue, Vault/KMS, OpenTelemetry full tracing은 후속 후보로 남겼다.
- Production Hardening drill은 local Docker Compose와 sample evidence 기준이며, destructive fault injection을 기본 실행하지 않는다.
- Recovery, write resume, 원장 보정, partner key retirement는 자동 실행이 아니라 수동 승인 경계로 남긴다.

## 13. 최종 요약

Core Consistency Track에서는 금융 이벤트 정합성 처리 시스템을 구현했고, Operations Evidence Track에서는 모니터링, DR Drill, 보안 통제, 장애 대응 Runbook까지 정리했다.
운영 확장 흐름은 Incident Runbook 정리까지 완료했으며, 추가 문서는 새로운 Phase가 아니라 운영 판단과 포트폴리오 evidence를 보완하는 supporting documents로 관리한다.
Production Hardening Track은 운영 확장 종료 이후의 후속 보완 트랙으로, PostgreSQL 장애 중 성공 응답 금지, 자동 진단과 수동 승인 경계, 민감 데이터의 AI-safe 처리 원칙을 문서화하고 일부 안전장치를 구현한다.
