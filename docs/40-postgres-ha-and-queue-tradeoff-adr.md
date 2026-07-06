# ADR: PostgreSQL HA and Durable Queue Trade-off

## Status

Proposed for Production Hardening Track.

이번 브랜치에서는 PostgreSQL HA 또는 durable queue를 구현하지 않는다.
현재 PostgreSQL transaction 중심 설계를 유지하면서, 후속 구현 판단을 위한 trade-off를 문서화한다.

## Context

이 프로젝트는 PostgreSQL을 최종 Source of Truth로 둔다.
Redis는 lock/cache/fallback을 위한 보조 계층이며, Redis 장애는 degraded mode로 처리할 수 있다.

하지만 PostgreSQL 자체가 down되면 신규 금융 write를 확정 처리할 수 없다.
이때 선택지는 크게 세 가지다.

1. Single PostgreSQL + fail-closed/write suspend
2. PostgreSQL primary/standby HA
3. API 앞 또는 뒤에 durable queue 도입

각 선택지는 API 응답 의미, commit durability, 운영 복잡도, reconciliation 책임을 바꾼다.

## RPO/RTO target

현재 로컬 프로젝트는 PostgreSQL HA를 구현하지 않았으므로 DB 장애 중 RPO 0을 기술적으로 보장한다고 주장하지 않는다.
대신 PostgreSQL commit 이전 성공 응답 금지, 동일 idempotency key 재시도, 복구 후 consistency gate를 보장 대상으로 둔다.

| 항목 | 현재 목표 | Queue-first 도입 시 |
| --- | --- | --- |
| RPO | commit 전 성공 응답 금지, 복구 후 중복 반영 0 검증 | queue durability 기준으로 수신 RPO와 ledger posting RPO 분리 |
| RTO | 로컬 drill에서 DB stop/start 후 1~3분 내 readiness 회복과 consistency check 완료 목표 | API accept RTO와 consumer posting RTO 분리 |
| Write resume | consistency gate와 recovery case 검토 후 사람 승인 | DLQ/replay/reconciliation 검토 후 사람 승인 |
| In-doubt event | recovery case로 격리 | queue offset, consumer idempotency, DB evidence를 함께 대조 |

## Decision

1차 Production Hardening에서는 다음을 선택한다.

- PostgreSQL write 불가 시 신규 금융 write는 `503` + `Retry-After`로 fail-closed 한다.
- write suspend, recovery mode, recovery case, reconciliation을 먼저 설계한다.
- PostgreSQL HA와 durable queue는 ADR과 후속 구현 후보로 관리한다.
- queue 도입 시 API 응답 의미를 `COMPLETED`가 아니라 `ACCEPTED`로 분리해야 한다.

## Option A. Single PostgreSQL + fail-closed

- 선택한 정책: DB write 불가 시 신규 거래를 성공 처리하지 않는다.
- 대안: Redis/memory/file에 임시 저장 후 나중에 반영한다.
- 선택 이유: 처리 여부를 증명할 수 없는 성공 응답을 만들지 않는다.
- 포기한 것: DB 장애 중 수신 성공률.
- 보완 전략: `Retry-After`, idempotency key 유지, recovery case, 복구 후 consistency gate.
- 면접 답변용 한 문장: PostgreSQL이 Source of Truth인 구조에서는 DB 장애 중 성공 응답을 주지 않고, 재시도 가능한 실패로 반환하는 것이 정합성에 더 안전합니다.

## Option B. PostgreSQL primary/standby HA

구조:

```text
API
 -> PostgreSQL Primary
 -> PostgreSQL Standby
```

- 선택한 기술 후보: PostgreSQL streaming replication, managed DB HA.
- 대안: single PostgreSQL + backup/restore.
- 선택 이유: DB 자체가 단일 장애점이 되는 것을 줄인다.
- 포기한 것: 운영 복잡도 증가, failover 검증 필요.
- 보완 전략: read/write split 금지 또는 제한, primary write만 허용, failover 후 consistency gate 강제.
- 면접 답변용 한 문장: PostgreSQL HA는 availability를 높이지만, failover 후 어떤 primary가 최종 기준인지 확인하기 전에는 write resume을 허용하면 안 됩니다.

주의:

- standby는 read-only query를 받을 수 있지만 replication lag가 있을 수 있다.
- failover 직후 stale connection이 남을 수 있다.
- application은 failover 중 `503`과 retry를 안전하게 처리해야 한다.

## Option C. Synchronous replication

- 선택한 기술 후보: synchronous standby 또는 quorum-based synchronous replication.
- 대안: asynchronous streaming replication.
- 선택 이유: 금융 원장성 write의 RPO를 낮출 수 있다.
- 포기한 것: commit latency 증가, standby 장애 시 commit 대기 가능성.
- 보완 전략: timeout 정책, write suspend, critical ledger path에만 강한 durability 적용 검토.
- 면접 답변용 한 문장: synchronous replication은 내구성을 높이지만 commit latency와 가용성 trade-off가 있어 원장 write path 중심으로 제한 적용을 검토해야 합니다.

## Option D. Managed DB HA

- 선택한 기술 후보: AWS RDS Multi-AZ, Cloud SQL HA 등.
- 대안: Docker Compose로 Patroni/repmgr 직접 구성.
- 선택 이유: 실제 운영에서는 DB HA 자체를 managed service에 위임하는 경우가 많다.
- 포기한 것: DB cluster 내부 구현 경험.
- 보완 전략: application readiness, retry, stale connection 처리, failover 후 consistency gate를 검증한다.
- 면접 답변용 한 문장: DB HA를 managed service에 맡기더라도 애플리케이션은 failover 중 connection error와 복구 후 정합성 검증을 직접 책임져야 합니다.

## Option E. Durable queue-first architecture

구조:

```text
External System
 -> API
 -> Durable Queue
 -> Consumer
 -> PostgreSQL
```

- 선택한 기술 후보: Kafka, SQS, RabbitMQ 등 durable queue.
- 대안: API가 직접 PostgreSQL transaction을 수행한다.
- 선택 이유: PostgreSQL이 잠시 down되어도 이벤트 수신 자체는 보존할 수 있다.
- 포기한 것: API 응답 시점에 원장 반영 완료를 보장하기 어렵다.
- 보완 전략: 응답 의미를 `ACCEPTED`와 `COMPLETED`로 분리, consumer idempotency, DLQ, replay, reconciliation 필요.
- 면접 답변용 한 문장: Queue를 앞에 두면 수신 가용성은 높아지지만, API 계약을 처리 완료가 아니라 수신 완료로 바꿔야 합니다.

## API contract impact

| Architecture | API 응답 의미 | 장점 | 위험 |
| --- | --- | --- | --- |
| Direct PostgreSQL transaction | commit 결과 기준 `COMPLETED/FAILED` | 단순하고 정합성 증명 쉬움 | DB down 중 수신 불가 |
| Direct + fail-closed | `503` + retry | 처리 여부 불명확 성공 방지 | 장애 중 성공률 낮음 |
| Queue-first | `202 Accepted` | DB down 중 수신 가능 | 처리 완료와 수신 완료 혼동 위험 |
| HA primary write | primary commit 결과 | DB 장애 window 축소 | failover 검증 복잡 |

## Consequences

- 현재 후속 보완의 우선순위는 DB HA cluster 구축보다 application fail-closed와 recovery workflow다.
- queue-first는 좋은 고도화 후보지만 API contract와 consumer/reconciliation 설계가 함께 바뀐다.
- PostgreSQL HA를 쓰더라도 write resume 전 consistency gate는 필요하다.
- failover in-doubt 이벤트는 recovery case로 격리해야 한다.

## Follow-up implementation candidates

- DB down drill: `503` + `Retry-After`, no successful idempotency record.
- failover-like stale connection drill.
- recovery mode and write resume approval gate.
- optional managed DB HA runbook.
- optional queue-first ADR update with API contract split.
