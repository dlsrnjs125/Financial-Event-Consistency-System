# Production Hardening Roadmap

> 이 문서는 Production Hardening Track의 시작점이다.
> 기존 Dev/Ops Track에서 검증한 정합성 원칙을 유지하면서, 실제 운영 환경에서 PostgreSQL 장애, 자동 진단, 복구 승인, 민감 데이터 보호, latency attribution 기준을 보완한다.

## 1. 왜 Production Hardening Track이 필요한가

기존 프로젝트는 중복 요청, Redis 장애, 배포 실패, DR Drill 상황에서도 PostgreSQL 기준 최종 정합성을 유지하는지를 검증했다.

하지만 실제 운영에서는 Redis보다 더 강한 hard dependency인 PostgreSQL 자체가 down되거나 불안정해질 수 있다.
PostgreSQL은 Source of Truth이지만, 항상 write 가능한 저장소라는 뜻은 아니다.
PostgreSQL write path가 불가능한 순간에는 신규 금융 거래를 확정 처리하지 않아야 한다.

또한 장애 로그와 metric이 쌓였을 때 운영자가 모든 것을 수동으로 판단하면 대응이 느려지고 누락이 생긴다.
반대로 금전 상태를 바꾸는 복구까지 자동화하면 사고 영향이 커질 수 있다.
따라서 자동화는 탐지, 분류, 차단, 증거 수집, 복구 후보 생성까지 담당하고, write resume, 원장 보정, 고객 영향 판단은 사람이 승인하는 경계를 문서화해야 한다.

## 2. 기존 프로젝트에서 이미 검증한 것

| 영역 | 이미 검증한 내용 | 근거 |
| --- | --- | --- |
| Idempotency | 같은 `Idempotency-Key`와 같은 body의 재시도는 같은 결과 반환 | `docs/11-api-response-policy.md`, `docs/15-api-contract.md` |
| 최종 정합성 | PostgreSQL unique constraint와 transaction을 기준으로 중복 ledger 방지 | `docs/03-consistency-rules.md`, `docs/12-data-model-spec.md` |
| Redis 장애 | Redis down/degraded 상황에서도 PostgreSQL 기준 처리 | `docs/23-failure-recovery-runbook-drill.md` |
| Duplicate storm | k6 duplicate storm과 정합성 SQL로 중복 반영 0건 검증 | `docs/16-performance-measurement-design.md` |
| 배포 복구 | Blue-Green rollback과 smoke/consistency gate | `docs/phase-12-blue-green-rollback.md` |
| DR Drill | PostgreSQL dump restore 후 count-only consistency SQL 검증 | `docs/22-postgres-backup-restore-drill.md` |
| Incident Runbook | Redis, DB pressure, Nginx, consistency, security incident 대응 기준 | `docs/26-incident-runbook-index.md` |
| SLO/SLI | 정합성 위반 0건, PostgreSQL down SEV1 기준 | `docs/29-slo-sli-error-budget.md` |

## 3. 아직 부족한 것

| 부족한 영역 | 현재 한계 | Production Hardening에서 보완할 방향 |
| --- | --- | --- |
| PostgreSQL 장애 정책 | PostgreSQL 장애를 connection exhaustion 중심으로 다룸 | DB down, pressure, failover, WAL/disk 장애별 write policy 분리 |
| Write suspend | 신규 금융 write를 언제 의도적으로 닫을지 기준 부족 | `WRITE_SUSPENDED`, `READ_ONLY`, `RECOVERY_MODE` 운영 상태 정의 |
| 자동 진단 | metric/log를 사람이 직접 해석 | deterministic rule 기반 Incident Analyzer 설계 |
| Recovery case | 잘못된 상태 차단 이후 승인/복구 흐름 부족 | recovery case lifecycle, quarantine, reconciliation 설계 |
| Stale PROCESSING | 처리 중 멈춘 idempotency/event 복구 기준 부족 | 자동 재처리, 자동 완료, 수동 승인 조건 분리 |
| AI 활용 | 실제 금융 데이터를 AI에 넘길 때의 기준 부족 | 민감 데이터 등급, 금지 데이터, sanitized context 기준 정의 |
| 데이터 보호 기술 구분 | masking/hash/HMAC/encryption/tokenization 용도 혼재 가능 | 용도별 책임과 trade-off 분리 |
| DB HA/Queue 판단 | 단일 DB, HA, queue-first architecture trade-off 미정리 | ADR로 응답 의미와 정합성 책임 명확화 |
| Latency attribution | p95/p99 상승만으로 내부/외부 책임 구간을 분리하기 어려움 | Nginx, app phase, DB/Redis, outbound dependency, blackbox probe 기준 정의 |

## 4. 핵심 질문

- Redis가 죽어도 PostgreSQL로 정합성을 지킬 수 있다는 설계 이후, PostgreSQL 자체가 down되면 시스템은 무엇을 약속하고 무엇을 거절해야 하는가?
- DB 장애 중 성공 응답을 반환하지 않는 fail-closed 정책을 외부 시스템 retry contract와 어떻게 연결할 것인가?
- 장애 로그와 metric 중 어떤 신호는 자동 분류할 수 있고, 어떤 판단은 사람이 승인해야 하는가?
- 잘못된 상태를 차단한 뒤 affected account/client/event를 어떻게 격리하고 recovery case로 관리할 것인가?
- stale `PROCESSING` 상태는 언제 자동 복구하고, 언제 수동 승인으로 넘길 것인가?
- 실제 금융 데이터가 포함된 incident context에서 AI에게 넘길 수 있는 데이터와 금지 데이터는 무엇인가?
- DB HA, synchronous replication, managed HA, durable queue 도입은 현재 PostgreSQL transaction 중심 설계와 어떤 trade-off가 있는가?
- 외부 시스템이 "API가 느리다"고 신고했을 때 내부 처리, edge/network, 외부 dependency 중 어느 구간의 지연인지 어떻게 좁힐 것인가?

## 5. Phase별 진행 계획

| Phase | 목표 | 주요 산출물 | Design Status | Implementation Status |
| --- | --- | --- | --- | --- |
| PH Phase 0 | Production Readiness Gap Analysis | 이 문서, 로드맵 연결 | Drafted | Pending |
| PH Phase 1 | PostgreSQL Failure Policy & Write Suspend 설계 | `36-postgres-failure-and-write-suspend-policy.md` | Drafted | Pending |
| PH Phase 2 | Incident Diagnosis Automation 설계 | `37-incident-diagnosis-automation-design.md` | Drafted | Pending |
| PH Phase 3 | Recovery Case / Quarantine / Manual Approval 설계 | `38-recovery-case-quarantine-and-reconciliation-design.md` | Drafted | Pending |
| PH Phase 4 | Stale PROCESSING Recovery & Reconciliation 설계 | `38-recovery-case-quarantine-and-reconciliation-design.md` | Drafted | Pending |
| PH Phase 5 | Sensitive Data Protection & AI Safe Governance 설계 | `39-sensitive-data-ai-governance-and-encryption-tradeoff.md` | Drafted | Pending |
| PH Phase 6 | Partner Secret Rotation & HMAC Hardening 설계 | `39-sensitive-data-ai-governance-and-encryption-tradeoff.md`, `docs/28-secret-management-policy.md` | Drafted | Pending |
| PH Phase 7 | PostgreSQL HA / Durable Queue Trade-off ADR | `40-postgres-ha-and-queue-tradeoff-adr.md` | Drafted | Pending |
| PH Phase 8 | Production Hardening Drill 구현 계획 | 후속 Makefile/script/test 후보 | Drafted | Pending |
| PH Phase 9 | Latency Attribution / External Dependency Diagnosis 설계 | `41-latency-attribution-and-external-dependency-diagnosis.md` | Drafted | Pending |

## 6. 자동화 가능한 부분과 사람이 해야 하는 부분

자동화 가능한 영역:

- write suspend mode 활성화 후보 판단
- 특정 account/client quarantine 후보 생성
- `Retry-After` 응답 정책 활성화 후보 제안
- background reprocessor 일시 중지 후보 제안
- consistency SQL 실행과 count-only 결과 수집
- recovery case 생성
- incident report 초안 생성
- Prometheus query, k6 summary, structured log evidence 수집
- sanitized AI context 생성
- latency attribution evidence bundle 생성

사람이 승인해야 하는 영역:

- PostgreSQL failover promote
- backup restore 실행
- 원장 보정 SQL 또는 compensation ledger 생성
- affected customer/partner 영향도 확정
- 외부 공지 여부 결정
- partner secret rotation 최종 승인
- write resume 승인
- AI가 제안한 복구 방안 채택

핵심 기준:

```text
자동화는 탐지, 차단, 증거 수집, 후보 생성까지 담당한다.
금전 상태를 바꾸는 복구와 외부 책임이 생기는 판단은 사람이 승인한다.
```

## 7. README 관리 원칙

README는 포트폴리오 요약과 핵심 링크만 둔다.
Production Hardening의 상세 정책, trade-off, lifecycle, runbook 초안은 `docs/`를 canonical source로 관리한다.

README에는 다음 수준만 기록한다.

- PostgreSQL write 불가 시 신규 금융 거래는 성공으로 응답하지 않는다.
- 자동화는 탐지, 차단, 증거 수집, 복구 후보 생성까지 담당한다.
- 원장 보정, write 재개, 고객 영향 판단은 사람이 승인한다.
- 자세한 설계는 `docs/35-*` ~ `docs/40-*` 문서에서 관리한다.
- latency attribution과 외부 dependency 진단은 `docs/41-*` 문서에서 관리한다.
