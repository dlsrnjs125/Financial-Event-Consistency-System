# PH8 PostgreSQL HA / Durable Queue Decision Evidence

## 1. Goal

PH8 adds deterministic decision evidence for PostgreSQL HA and durable queue trade-offs.

The goal is not to build HA infrastructure or queue middleware. The goal is to explain, with reproducible evidence, why the project currently keeps direct PostgreSQL transaction processing plus fail-closed/write suspend.

## 2. Why This Is Not an Implementation Phase

PH8 does not attach Kafka, RabbitMQ, Patroni, repmgr, RDS Multi-AZ, or Cloud SQL HA because the current API contract is based on PostgreSQL commit-backed `COMPLETED` responses.

Queue-first architecture changes more than infrastructure:

- API response semantics must split `ACCEPTED` from `COMPLETED`.
- Consumer idempotency becomes part of correctness.
- DLQ, replay, offset checkpoint, and reconciliation evidence become mandatory.
- Posting completion and enqueue durability need separate RPO/RTO boundaries.

Implementing a queue without this contract split would make the financial consistency story less clear.

## 3. Current Architecture Boundary

Current write path:

```text
External Financial System
-> API
-> PostgreSQL transaction
-> COMPLETED response only after commit
```

If PostgreSQL write path is unavailable:

```text
PostgreSQL unavailable
-> 503 Service Unavailable
-> Retry-After
-> same Idempotency-Key/body retry
```

## 4. Compared Options

| Option | Summary |
| --- | --- |
| Direct PostgreSQL transaction + fail-closed | Current choice. Simple consistency explanation, lower outage availability. |
| PostgreSQL primary/standby HA | Availability candidate. Still needs failover consistency gate. |
| Synchronous replication | Lower RPO candidate. Adds commit latency and write stall risk. |
| Managed DB HA | Production candidate. Reduces DB operations burden, not app responsibility. |
| Durable queue-first | V2 candidate. Improves accept availability but changes API meaning. |

## 5. Decision Matrix Criteria

The report scores each option from 1 to 5.

These scores are deterministic project-fit signals, not production benchmarks.

| Criterion | Meaning |
| --- | --- |
| Availability | Whether the option improves write/accept availability |
| Consistency explainability | Whether correctness is easy to explain and verify |
| Operational complexity | Higher score means easier within this local project |
| Cost | Higher score means lower local/portfolio cost |
| Local portfolio fit | Whether it produces reproducible evidence without external services |

## 6. API Contract Impact

The current API can return `COMPLETED` because it processes the transaction directly against PostgreSQL.

Queue-first must split responses:

- `ACCEPTED`: event durably accepted by queue
- `COMPLETED`: consumer processed the event and PostgreSQL commit evidence exists

This split is not cosmetic. Without it, an external partner could treat queued-but-not-posted events as completed financial ledger updates.

## 7. Consistency and Recovery Responsibility

| Option | Responsibility |
| --- | --- |
| Direct PostgreSQL | DB constraints, transaction boundary, write suspend, recovery case |
| PostgreSQL HA | primary identity, failover gate, stale connection handling, write resume approval |
| Synchronous replication | quorum/standby health, timeout policy, write suspend on sync failure |
| Managed DB HA | provider failover plus app readiness/retry/consistency gate |
| Queue-first | consumer idempotency, DLQ, replay approval, offset evidence, reconciliation |

Automation can generate evidence and propose actions.
Failover promote, write resume, ledger correction, customer impact, and queue replay remain human-approved.

## 8. Generated Evidence Report

Generated files:

```text
reports/architecture/ph8-ha-queue-tradeoff/sample-ha-queue-decision-report.json
reports/architecture/ph8-ha-queue-tradeoff/sample-ha-queue-decision-report.md
```

The report includes:

- `run_id`
- `generated_at`
- `phase`
- `current_decision`
- `options`
- `decision_matrix`
- `recommendation`
- `manual_approval_required`
- `non_scope`
- `follow_up_candidates`

## 9. CLI and Makefile

CLI:

```bash
python3 scripts/ph8_ha_queue_decision_matrix.py demo
python3 scripts/ph8_ha_queue_decision_matrix.py validate --input reports/architecture/ph8-ha-queue-tradeoff/sample-ha-queue-decision-report.json
```

Makefile:

```bash
make ph8-ha-queue-decision-demo
make ph8-ha-queue-decision-validate
make ph8-architecture-check
```

## 10. Verification Criteria

Validator checks:

- required top-level fields
- all five architecture options
- score range 1~5
- non-empty `current_decision`
- queue-first `ACCEPTED`/`COMPLETED` split
- HA failover consistency gate and write resume approval
- no raw account number, idempotency key, Authorization, secret, signature, password, raw request body, or database URL
- no claim that queue enqueue guarantees ledger completion
- no claim that HA removes consistency gate

## 11. Troubleshooting Notes

### Queue-First Raises Availability But Not Completion

- 문제: durable queue를 앞에 두면 DB 장애 중에도 API가 요청을 받을 수 있지만, 원장 반영 완료를 의미하지 않는다.
- 원인: queue enqueue와 PostgreSQL ledger commit은 서로 다른 durability boundary다.
- 해결: PH8에서는 queue-first를 별도 V2 후보로 분리하고 `ACCEPTED`/`COMPLETED` 응답 의미 분리를 필수 조건으로 둔다.
- 검증: validator가 queue-first option에 `ACCEPTED`와 `COMPLETED`가 없으면 실패한다.
- README에 넣지 않은 이유: README에는 한 문장 요약과 문서 링크만 둔다.

### HA Still Needs Write Resume Approval

- 문제: HA를 붙이면 failover 후 바로 write를 열어도 된다고 오해할 수 있다.
- 원인: stale connection, replication lag, split-brain 가능성은 애플리케이션 evidence로 확인해야 한다.
- 해결: HA option의 required controls에 consistency gate와 write resume approval을 둔다.
- 검증: validator가 HA option에 해당 문구가 없으면 실패한다.
- README에 넣지 않은 이유: failover 운영 책임은 ADR에서 관리한다.

### Synchronous Replication Increases Commit Cost

- 문제: synchronous replication을 RPO만 보고 정답으로 선택할 수 있다.
- 원인: standby/quorum ack를 기다리면 commit latency와 write stall 위험이 커진다.
- 해결: RPO 개선 후보로만 두고, ledger-critical path 적용 여부를 후속 후보로 분리한다.
- 검증: decision matrix가 availability, explainability, complexity, cost를 분리해 보여준다.
- README에 넣지 않은 이유: replication trade-off는 상세 ADR 범위다.

### Managed DB HA Does Not Remove App Responsibility

- 문제: RDS Multi-AZ 같은 managed HA가 있으면 애플리케이션 복구 로직이 필요 없다고 볼 수 있다.
- 원인: provider는 DB failover를 돕지만 app retry, readiness, stale connection, write resume은 별도 책임이다.
- 해결: managed DB HA를 recommended later로 두고 app control을 report에 명시한다.
- 검증: report validator와 ADR option table에서 consistency gate와 write resume approval을 확인한다.
- README에 넣지 않은 이유: cloud provider별 세부는 README 요약 범위를 넘는다.

### Scores Can Look Like Benchmarks

- 문제: 1~5 score가 실제 성능 측정값처럼 보일 수 있다.
- 원인: 숫자 형태의 decision evidence는 절대 지표로 오해되기 쉽다.
- 해결: score는 deterministic project-fit signal이며 benchmark가 아니라고 report와 docs에 명시한다.
- 검증: report의 decision matrix note와 ADR 설명을 확인한다.
- README에 넣지 않은 이유: README에는 score 전체를 넣지 않는다.

### README Should Not Become the ADR

- 문제: README에 HA/Queue 비교표를 넣으면 포트폴리오 요약성이 떨어진다.
- 원인: README는 첫 화면 안내이고 ADR은 판단 근거의 source of truth다.
- 해결: README에는 PH8 한 문장, 명령 1~2개, docs 링크만 추가한다.
- 검증: 상세 비교표는 docs/40과 docs/50에만 둔다.
- README에 넣지 않은 이유: 이 항목 자체가 README 최소화 원칙을 설명한다.

## 12. Limits and Next Steps

Limits:

- no HA cluster implementation
- no durable queue implementation
- no cloud resource provisioning
- no automatic failover promote
- no automatic write resume

Next candidates:

- managed DB HA runbook
- failover-like stale connection drill
- queue-first API V2 ADR
- consumer idempotency and DLQ replay design
- split RPO/RTO targets for API accept and ledger posting
