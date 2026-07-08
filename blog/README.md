# Financial Event Consistency Blog Series

이 디렉터리는 프로젝트 구현 일지 전체를 공개 블로그 순서로 그대로 나열하기보다, 면접이나 포트폴리오에서 설명력이 높은 글을 중심으로 재정리한다.

공개 글의 기준은 기능 목록이 아니라 다음 네 가지다.

- 금융 이벤트 정합성 문제를 어떻게 정의했는가
- 중복 요청, 장애, 재시도, 배포, 복구 상황에서 어떤 설계 판단을 했는가
- 실제로 막힌 지점과 트러블슈팅이 무엇이었는가
- 어떤 evidence로 검증했는가

## 공개 권장 시리즈

| No. | 공개 제목 | 현재 원문 / 통합 대상 | 공개 판단 |
| --- | --- | --- | --- |
| 01 | 금융 이벤트 시스템에서 가장 무서운 장애는 500이 아니라 중복 반영이었다 | [01](01-why-financial-event-consistency.md) | 공개 |
| 02 | 거래 상태를 코드가 아니라 규칙으로 막은 이유 | [02](02-domain-model-and-state-machine.md), [06](06-state-transition-test-strategy.md) | 통합 공개 |
| 03 | Idempotency Key만 같다고 같은 거래라고 볼 수 있을까? | [03](03-idempotency-key-design.md) | 공개 |
| 04 | Redis Lock을 믿지 않고 PostgreSQL Unique Constraint를 마지막 방어선으로 둔 이유 | [04](04-postgresql-transaction-unique-constraint.md), [05](05-redis-lock-cache-fallback.md) | 통합 공개 |
| 05 | p99가 느려져도 원장이 두 번 반영되면 안 된다 | [07](07-k6-duplicate-storm-performance-test.md) | 공개 |
| 06 | API p99가 느려졌을 때 코드 문제인지 DB 문제인지 어떻게 구분할까? | [08](08-prometheus-grafana-observability.md), [13](13-why-infra-metrics-matter.md) | 통합 공개 |
| 07 | Redis 장애는 버티고, PostgreSQL 장애는 막는다 | [09](09-docker-compose-failure-simulation.md), [20](20-failure-recovery-runbook-drill.md) 일부 | 통합 공개 |
| 08 | 배포 Gate는 코드를 고치는 명령이 아니라 실패를 알려주는 명령이어야 했다 | [10](10-ci-cd-consistency-deployment-gate.md) | 공개 |
| 09 | 배포 실패 시 DB를 되돌리지 않고 트래픽만 Blue로 되돌린 이유 | [11](11-blue-green-rollback-simulation.md) | 공개 |
| 10 | PostgreSQL 백업은 만들어지는 것보다 복구되는 것이 중요하다 | [15](15-postgresql-backup-restore-drill.md) | 공개 |
| 11 | `/metrics`와 `/ready`를 public API에서 숨긴 이유 | [14](14-nginx-as-financial-ops-gateway.md), [18](18-internal-network-access-control.md) | 통합 공개 |
| 12 | 장애를 복구했다는 말만으로는 부족했다 | [19](19-incident-runbook-oncall-simulation.md), [20](20-failure-recovery-runbook-drill.md), [21](21-alerting-incident-response-runbook.md), [22](22-incident-timeline-postmortem-drill.md) | 통합 공개 |
| 13 | PostgreSQL이 죽었을 때 성공 응답도, 장애 기록 유실도 막고 싶었다 | [23](23-postgresql-down-write-suspend-drill.md), [24](series/24-production-hardening-incident-artifact.md) | 통합 공개 |
| 14 | 장애를 찾았다고 바로 고치면 더 위험했다 | [25](series/25-production-hardening-incident-analyzer.md), [26](series/26-production-hardening-recovery-case-quarantine.md), [27](series/27-production-hardening-stale-processing-reconciliation.md) | 통합 공개 |
| 15 | AI 요약과 HMAC Rotation을 붙이기 전에 먼저 막아야 했던 것들 | [28](series/28-ai-safe-incident-context-sanitizer.md), [29](series/29-partner-secret-rotation-hmac-hardening.md) | 통합 공개 |
| 16 | k6 p99가 튀었을 때 바로 DB 탓을 하면 안 되는 이유 | [32](series/32-latency-attribution-external-dependency-diagnosis.md), [33](series/33-latency-drill-evidence-runner.md) | 선택 공개 |

## 공개 목록에서 제외하거나 흡수할 글

| 글 | 처리 | 이유 |
| --- | --- | --- |
| [12. Project Retrospective](12-project-retrospective.md) | 공개 시리즈 제외 | 전체 회고 성격이라 README와 중복된다. |
| [16. Ansible Operation Automation](16-ansible-operation-automation.md) | 공개 시리즈 제외 | optional enhancement 초안이며 구현 evidence가 약하다. |
| [17. Windows PowerShell Ops Check](17-windows-powershell-ops-check.md) | 공개 시리즈 제외 | 운영자 단말 지원 후보로, core consistency/evidence 흐름과 거리가 있다. |
| [18. Internal Network Access Control](18-internal-network-access-control.md) | 11편에 흡수 | public/internal endpoint 접근 제어는 14편과 함께 읽는 편이 자연스럽다. |
| [31. Production Hardening Drill Plan](series/31-production-hardening-drill-plan.md) | 공개 시리즈 단독 제외 | docs/report 성격이 강하며 PH9 상세는 docs/51에서 관리한다. |
| [33. Latency Drill Evidence Runner](series/33-latency-drill-evidence-runner.md) | 16편에 흡수 | PH10 latency attribution과 함께 읽을 때 설명력이 높다. |

## 공개 글에서 반드시 살릴 트러블슈팅

- 같은 `Idempotency-Key` + 다른 body를 `409 Conflict`로 처리한 이유
- Redis degraded 정책과 Docker Compose hard dependency 설정이 충돌했던 문제
- `final-check`가 파일을 수정하면 안 된다는 CI Gate 문제
- Blue-Green rollback은 DB rollback이 아니라 traffic rollback이라는 판단
- `pg_dump` 생성보다 restore DB 검증이 중요하다는 DR Drill 판단
- public Nginx에서 `/metrics`, `/ready`, `/docs`, `/openapi.json`을 차단한 이유
- CI에서는 Redis stop/start drill을 돌리지 않고 로컬 evidence와 CI validation을 분리한 이유
- PostgreSQL down 중 write success를 주지 않고 `503 + Retry-After`로 fail-closed한 이유
- `write-suspend-state.json` 손상 시 artifact 생성을 실패시키지 않고 `invalid_state_json`으로 남긴 이유
- `manifest.json` 누락을 sanitization risk가 아니라 insufficient evidence로 분리한 이유
- stale `PROCESSING`을 자동 완료/실패 처리하지 않은 이유
- AI-safe context redaction summary에도 raw value를 남기지 않은 이유
- HMAC next secret을 실제 write API가 아니라 dry-run에서만 허용한 이유
- k6 p99 상승을 바로 DB root cause로 단정하지 않은 이유
