# ADR: PostgreSQL HA and Durable Queue Trade-off

## 1. Status

Accepted for PH8 decision evidence.

PH8 does not implement PostgreSQL HA, Patroni, repmgr, Kafka, RabbitMQ, SQS, or cloud database resources. It documents the architectural trade-off and generates deterministic evidence for why the current project keeps direct PostgreSQL transaction processing with fail-closed/write suspend.

## 2. Context

This project treats PostgreSQL as the final Source of Truth for `TransactionEvent`, `LedgerEntry`, `Account.balance`, and `IdempotencyRecord`.

Redis improves duplicate-request mitigation and performance, but it is not the consistency authority. When the PostgreSQL write path is unavailable, the API must not return a successful financial completion response.

The hard question is what should happen next:

- keep direct PostgreSQL transaction processing and fail closed
- introduce PostgreSQL HA to reduce outage windows
- use synchronous replication to reduce RPO
- use managed DB HA to move cluster operations to a provider
- move to durable queue-first ingestion

Each option changes API response semantics, recovery evidence, and operational responsibility.

## 3. Current Decision

Current PH8 decision:

```text
Maintain direct PostgreSQL transaction + fail-closed/write suspend now.
Keep PostgreSQL HA as a production availability follow-up.
Treat durable queue-first architecture as a separate V2/API-contract candidate.
```

Rationale:

- A `COMPLETED` response should mean PostgreSQL commit evidence exists.
- If PostgreSQL cannot accept writes, the safer response is `503 + Retry-After`.
- Queue-first ingestion changes the API response from "ledger posting completed" to "event accepted for later processing".
- HA does not remove the need for failover consistency gate and human write resume approval.

## 4. Architecture Options

| Option | Shape | Summary |
| --- | --- | --- |
| A. Current direct PostgreSQL + fail-closed | `External System -> API -> PostgreSQL` | Simple consistency story. DB down returns `503 + Retry-After`. |
| B. PostgreSQL primary/standby HA | `API -> PostgreSQL Primary -> Standby` | Reduces DB single point of failure, but failover still needs validation. |
| C. Synchronous replication | `API -> Primary -> Sync standby/quorum` | Lowers RPO, increases commit latency and write-path coupling. |
| D. Managed DB HA | `API -> Managed HA database endpoint` | Outsources DB HA operations, not application recovery responsibility. |
| E. Durable queue-first | `External System -> API -> Durable Queue -> Consumer -> PostgreSQL` | Improves accept availability, but splits `ACCEPTED` from `COMPLETED`. |

## 5. API Contract Impact

| Architecture | Response Meaning | Contract Risk |
| --- | --- | --- |
| Direct PostgreSQL transaction | `COMPLETED` only after PostgreSQL commit | DB outage reduces write availability |
| Direct + fail-closed | `503 + Retry-After` means not completed | External systems must retry with same idempotency key/body |
| Primary/standby HA | `COMPLETED` remains primary commit based | Failover window can create stale connection and in-doubt cases |
| Synchronous replication | `COMPLETED` includes sync durability wait | Higher latency can increase timeout/retry pressure |
| Managed DB HA | `COMPLETED` remains DB commit based | App still owns readiness/retry/consistency gate |
| Durable queue-first | `ACCEPTED` means durable enqueue, `COMPLETED` means later ledger posting | Confusing accept with completion can cause financial incidents |

Queue-first must not reuse the current `COMPLETED` response for enqueue success. It needs a separate API contract and status lifecycle.

## 6. Consistency Responsibility

| Option | Consistency Authority | Additional Responsibility |
| --- | --- | --- |
| Direct PostgreSQL | PostgreSQL transaction and unique constraints | fail-closed, write suspend, recovery case |
| PostgreSQL HA | Current primary after failover validation | primary identity, stale connection handling, consistency gate |
| Synchronous replication | Primary commit plus sync acknowledgement | timeout policy, write suspend on quorum loss |
| Managed DB HA | Managed primary endpoint plus app validation | readiness, retry, consistency gate, write resume approval |
| Durable queue-first | Queue durability first, PostgreSQL ledger later | consumer idempotency, DLQ, replay approval, offset evidence, reconciliation |

## 7. Failure Mode Comparison

| Failure Mode | Direct Fail-Closed | PostgreSQL HA | Durable Queue-First |
| --- | --- | --- | --- |
| Primary DB down | `503 + Retry-After` | failover, then consistency gate | API can enqueue if queue is healthy |
| Commit uncertainty | no success response before commit | in-doubt window during failover | enqueue success and ledger posting are separate |
| Duplicate request | idempotency record + DB constraints | same, after primary identity confirmed | consumer idempotency plus DB constraints |
| Replay/retry | external retry with same key/body | same plus stale connection handling | queue replay/DLQ redrive approval |
| Recovery approval | write resume approval | failover promote and write resume approval | DLQ/replay and posting resume approval |

## 8. RPO / RTO Boundary

The current local project does not claim production RPO/RTO guarantees.

Current local drill target:

| Boundary | Local Evidence Goal |
| --- | --- |
| RPO | no successful response before PostgreSQL commit |
| RTO | DB stop/start drill recovers readiness and consistency checks in minutes |
| Write resume | human approval after consistency gate |
| In-doubt event | recovery case or out-of-band artifact |

Queue-first would split RPO/RTO:

- API accept RPO/RTO: whether the queue durably accepted the event
- Ledger posting RPO/RTO: whether the consumer committed the ledger update to PostgreSQL

Those two meanings must be visible in the API contract and evidence.

## 9. Operational Complexity

| Option | Complexity Source |
| --- | --- |
| Direct fail-closed | lower availability during DB outage |
| Primary/standby HA | failover runbook, stale connection recycling, split-brain prevention |
| Synchronous replication | commit latency, standby/quorum health, write stalls |
| Managed DB HA | cloud cost, provider behavior, app-level retry/readiness |
| Queue-first | consumer idempotency, DLQ, replay, offset checkpoint, reconciliation |

## 10. Cost and Local Portfolio Boundary

This repository stays local and reproducible. It does not provision cloud HA databases or queue infrastructure in PH8.

The goal is to show decision quality, not to attach every possible production dependency.

Managed HA and durable queues are valid production candidates, but adding them without changing API semantics and recovery evidence would make the consistency story weaker, not stronger.

## 11. Decision Matrix

PH8 adds a deterministic generator:

```bash
python3 scripts/ph8_ha_queue_decision_matrix.py demo
python3 scripts/ph8_ha_queue_decision_matrix.py validate --input reports/architecture/ph8-ha-queue-tradeoff/sample-ha-queue-decision-report.json
```

Scores are 1~5 project-fit signals, not production benchmarks.

| Criterion | Meaning |
| --- | --- |
| Availability | How much the option improves write/accept availability |
| Consistency explainability | How easy it is to explain and verify final correctness |
| Operational complexity | Higher score means easier to operate in this project scope |
| Cost | Higher score means lower cost for local portfolio scope |
| Local portfolio fit | How well the option fits deterministic local evidence |

## 12. Evidence Report

Generated sample:

```text
reports/architecture/ph8-ha-queue-tradeoff/sample-ha-queue-decision-report.json
reports/architecture/ph8-ha-queue-tradeoff/sample-ha-queue-decision-report.md
```

Makefile:

```bash
make ph8-ha-queue-decision-demo
make ph8-ha-queue-decision-validate
make ph8-architecture-check
```

The validator checks:

- required top-level fields
- required architecture options
- 1~5 score range
- queue-first `ACCEPTED`/`COMPLETED` split
- HA consistency gate and write resume approval
- no sensitive raw identifiers or secrets
- no claims that queue enqueue equals ledger completion
- no claims that HA removes consistency gate

## 13. Troubleshooting Notes

### Queue-First Cannot Return Completed

- 문제: queue-first 구조는 DB down 중 수신 가능성을 높이지만 현재 API의 `COMPLETED` 응답을 그대로 줄 수 없다.
- 원인: durable enqueue는 원장 반영 완료가 아니라 나중에 처리할 입력 보존이다.
- 해결: queue-first는 `ACCEPTED`와 `COMPLETED`를 분리하는 V2 contract 후보로 둔다.
- 검증: PH8 validator가 queue-first option에 `ACCEPTED`와 `COMPLETED` 의미 분리가 없으면 실패한다.
- README에 넣지 않은 이유: README에는 결론과 링크만 두고 API 의미 변화는 ADR에서 관리한다.

### HA Does Not Remove Consistency Gate

- 문제: HA를 붙이면 DB 장애가 사라진다고 오해할 수 있다.
- 원인: failover 중 stale connection, replication lag, primary identity 불확실성이 남는다.
- 해결: HA option에도 failover consistency gate와 write resume approval을 필수 control로 둔다.
- 검증: PH8 validator가 HA option에 consistency gate와 write resume approval이 없으면 실패한다.
- README에 넣지 않은 이유: HA 운영 세부 책임은 ADR의 범위다.

### Synchronous Replication Is Not Always Better

- 문제: RPO를 낮추는 선택을 항상 정답처럼 표현할 수 있다.
- 원인: synchronous replication은 commit latency와 standby/quorum 장애 시 write stall을 만든다.
- 해결: ledger-critical path에 제한 적용할지 후속 후보로 분리한다.
- 검증: decision matrix에 availability, explainability, complexity, cost를 별도 score로 둔다.
- README에 넣지 않은 이유: replication trade-off 표는 README 요약성을 해친다.

### Managed HA Still Leaves App Work

- 문제: managed DB HA를 쓰면 애플리케이션 복구 로직이 필요 없다고 오해할 수 있다.
- 원인: provider가 failover를 도와도 app은 retry/readiness/stale connection/write resume을 책임진다.
- 해결: managed HA option에도 readiness, consistency gate, write resume approval을 control로 둔다.
- 검증: report validator와 ADR option table에서 같은 requirement를 확인한다.
- README에 넣지 않은 이유: cloud provider 세부 운영은 문서 링크로 충분하다.

### Scores Are Not Benchmarks

- 문제: decision matrix score를 실제 성능 수치처럼 읽을 수 있다.
- 원인: 1~5 score는 프로젝트 범위 판단인데 숫자라 절대 지표처럼 보인다.
- 해결: report와 ADR에 deterministic project-fit signal이라고 명시한다.
- 검증: Markdown report와 JSON decision matrix note에 benchmark가 아니라고 남긴다.
- README에 넣지 않은 이유: score 설명 전체는 PH8 evidence 문서에서 관리한다.

## 14. Final Decision

Final PH8 decision:

- Keep direct PostgreSQL transaction processing.
- Keep fail-closed/write suspend for PostgreSQL write-path failure.
- Use `503 + Retry-After` instead of ambiguous success during DB outage.
- Treat PostgreSQL HA as a production availability follow-up.
- Treat durable queue-first ingestion as a separate V2/API-contract follow-up.

## 15. Follow-up Candidates

- managed DB HA runbook and failover drill
- stale connection readiness drill
- queue-first API V2 ADR
- consumer idempotency and DLQ replay design
- RPO/RTO split for API accept and ledger posting
