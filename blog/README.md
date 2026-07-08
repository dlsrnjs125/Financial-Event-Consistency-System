# Financial Event Consistency Blog Series

이 디렉터리는 프로젝트 구현 일지를 그대로 33편으로 공개하지 않고, 면접과 포트폴리오에서 설명력이 높은 흐름만 남긴 공개용 시리즈를 관리한다.

공개 기준은 기능 개수보다 다음 네 가지다.

- 금융 이벤트 정합성 문제를 어떻게 정의했는가
- 중복 요청, 장애, 재시도, 배포, 복구 상황에서 어떤 설계 판단을 했는가
- 실제로 막힌 지점과 트러블슈팅이 무엇이었는가
- 어떤 evidence로 검증했는가

## 공개 시리즈

| No. | 글 | 핵심 주제 |
| --- | --- | --- |
| 01 | [금융 이벤트 시스템에서 가장 무서운 장애는 500이 아니라 중복 반영이었다](series/01-duplicate-financial-event-problem.md) | 문제 정의, 중복 반영, Source of Truth |
| 02 | [거래 상태를 코드가 아니라 규칙으로 막은 이유](series/02-state-machine-domain-rules.md) | 상태 머신, invalid transition, 테스트 전략 |
| 03 | [Idempotency Key만 같다고 같은 거래라고 볼 수 있을까?](series/03-idempotency-key-request-hash.md) | request hash, replay, conflict |
| 04 | [Redis Lock을 믿지 않고 PostgreSQL Unique Constraint를 마지막 방어선으로 둔 이유](series/04-postgres-unique-constraint-redis-fallback.md) | unique constraint, Redis fallback, 최종 정합성 |
| 05 | [p99가 느려져도 원장이 두 번 반영되면 안 된다](series/05-k6-duplicate-storm-ledger-consistency.md) | duplicate storm, k6, ledger consistency |
| 06 | [API p99가 느려졌을 때 코드 문제인지 DB 문제인지 어떻게 구분할까?](series/06-observability-api-infra-metrics.md) | app metrics, infra metrics, 관측성 |
| 07 | [Redis 장애는 버티고, PostgreSQL 장애는 막는다](series/07-docker-compose-failure-dependency-policy.md) | dependency policy, Redis degraded, PostgreSQL hard dependency |
| 08 | [배포 Gate는 코드를 고치는 명령이 아니라 실패를 알려주는 명령이어야 했다](series/08-ci-cd-gate-non-mutating-final-check.md) | CI gate, final-check, non-mutating validation |
| 09 | [배포 실패 시 DB를 되돌리지 않고 트래픽만 Blue로 되돌린 이유](series/09-blue-green-traffic-rollback.md) | Blue-Green, traffic rollback, consistency gate |
| 10 | [PostgreSQL 백업은 만들어지는 것보다 복구되는 것이 중요하다](series/10-postgres-backup-restore-drill.md) | pg_dump, restore DB, DR drill |
| 11 | [`/metrics`와 `/ready`를 public API에서 숨긴 이유](series/11-nginx-public-internal-endpoint-boundary.md) | Nginx, public/internal boundary, endpoint exposure |
| 12 | [장애를 복구했다는 말만으로는 부족했다](series/12-runbook-alert-postmortem-evidence.md) | runbook, alert, postmortem, recovery evidence |
| 13 | [PostgreSQL이 죽었을 때 성공 응답도, 장애 기록 유실도 막고 싶었다](series/13-postgres-down-write-suspend-incident-artifact.md) | write suspend, fail-closed, out-of-band artifact |
| 14 | [장애를 찾았다고 바로 고치면 더 위험했다](series/14-analyzer-recovery-case-stale-reconciliation.md) | analyzer, recovery case, stale reconciliation |
| 15 | [AI 요약과 HMAC Rotation을 붙이기 전에 먼저 막아야 했던 것들](series/15-ai-safe-context-hmac-rotation-boundary.md) | AI-safe context, redaction, HMAC rotation |
| 16 | [k6 p99가 튀었을 때 바로 DB 탓을 하면 안 되는 이유](series/16-latency-attribution-drill-evidence.md) | latency attribution, drill evidence, consistency counters |

## 통합 및 제외 기준

| 기존 주제 | 처리 | 이유 |
| --- | --- | --- |
| Project Retrospective | 공개 시리즈 제외 | 전체 회고 성격이라 README와 중복된다. |
| Ansible Operation Automation | 공개 시리즈 제외 | optional enhancement 초안이며 핵심 정합성/evidence 흐름과 거리가 있다. |
| Windows PowerShell Ops Check | 공개 시리즈 제외 | 운영자 단말 지원 후보로, public portfolio narrative에서는 우선순위가 낮다. |
| Internal Network Access Control | 11편에 흡수 | public/internal endpoint 접근 제어는 Nginx gateway 글과 함께 읽는 편이 자연스럽다. |
| Production Hardening Drill Plan | 문서 산출물로 유지 | PH9 상세는 [docs/51](../docs/51-ph9-production-hardening-drill-plan.md)에서 관리하고, 블로그 흐름은 13~16편에 흡수한다. |
| Latency Drill Evidence Runner | 16편에 흡수 | PH10 latency attribution과 함께 읽을 때 문제-진단-evidence 흐름이 선명하다. |

## 공개 글에서 반드시 살린 트러블슈팅

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
