# AGENTS.md

## 1. Project Identity

This repository is the **Financial Event Consistency System**.

- It handles duplicate requests, retries, out-of-order events, and failure scenarios from external financial systems.
- The core goal is not fast feature delivery, but proving transaction consistency, idempotency, state transition safety, and failure resilience.
- PostgreSQL is the final Source of Truth for consistency.
- Redis is a performance optimization and duplicate-request mitigation layer, not the final consistency store.
- Every implementation should support the goals of **zero duplicate financial application** and **reproducible verification under failure scenarios**.

## 2. Current Repository Context

- `backend/`: FastAPI application, domain/service/repository/API/model/test code.
- `docs/`: design documents, roadmap, consistency rules, API contract, data model spec, test matrix.
- `blog/`: draft technical blog series.
- `infra/`: infrastructure and operational configuration.
- `scripts/`: development and operation helper scripts.
- `tests/k6/`: load-test scenarios.
- `Makefile`: entry point for local checks, tests, and runtime commands.
- `docker-compose.yml`: local PostgreSQL, Redis, API, and observability environment.
- `.github/workflows/`: CI pipelines.

## 3. Document Reading Priority

Do not read every document by default. Read only what is needed for the current task.

Always start with:

1. `README.md`
2. `docs/04-development-roadmap.md`
3. Docs directly related to the current Phase/task
4. `docs/03-consistency-rules.md`
5. `docs/12-data-model-spec.md`
6. `docs/13-state-transition-table.md`
7. `docs/14-test-case-matrix.md`
8. `docs/15-api-contract.md`

Phase-specific documents:

- Phase 2 Data Model:
  - `docs/12-data-model-spec.md`
- Phase 3 State Machine:
  - `docs/13-state-transition-table.md`
  - `docs/10-cancel-event-policy.md`
- Phase 4 Idempotency:
  - `docs/11-api-response-policy.md`
  - `docs/12-data-model-spec.md`
  - `docs/15-api-contract.md`
- Phase 5 Transaction/Ledger:
  - `docs/03-consistency-rules.md`
  - `docs/10-cancel-event-policy.md`
  - `docs/15-api-contract.md`
- Phase 6 Redis:
  - Read Redis-related docs if they exist.
  - If not, use `README.md` and `docs/04-development-roadmap.md` as the source of truth.
- Phase 7 Security:
  - `docs/06-security-design.md`
- Phase 8 Monitoring:
  - `docs/16-performance-measurement-design.md`
- Phase 9 Load Test:
  - `docs/14-test-case-matrix.md`
  - `docs/16-performance-measurement-design.md`
- Blog work:
  - Target `blog/` file
  - README technical blog series section
  - Only related docs

Token-saving rules:

- Do not read the entire `blog/` directory unless the task is explicitly broad blog work.
- Do not read the entire `docs/` directory unless explicitly requested.
- Identify the relevant docs first, then read only those docs.
- Before editing code, inspect only the directly related files.
- If information is already captured in this file, do not repeat long explanations.

## 4. Phase Boundary Rules

Most important rule: **do not implement features outside the requested Phase**.

### Phase 1

- FastAPI project foundation
- Configuration
- DB/Redis connection preparation
- Health/ready/metrics
- Basic logging and exception structure

### Phase 2

- SQLAlchemy ORM models
- Alembic migrations
- DB constraints and indexes
- Do not implement real transaction processing logic.

### Phase 3

- Transaction status enum
- State machine
- Invalid transition validation
- EventStateHistory persistence foundation
- Do not apply real account balance changes.

### Phase 4

- Idempotency-Key validation
- `request_hash`
- `IdempotencyRecordRepository`
- `IdempotencyService`
- `STARTED` / `ALREADY_PROCESSING` / `REPLAY_COMPLETED` / `REPLAY_FAILED`
- Do not implement balance changes or LedgerEntry creation.

### Phase 5

- TransactionEvent processing
- LedgerEntry creation
- Account balance updates
- Idempotency and DB transaction integration
- Do not implement Redis Lock/Cache.
- Do not implement HMAC authentication.

### Phase 6

- Redis Lock
- Redis Cache
- DB fallback
- Redis failure consistency guarantees
- PostgreSQL remains the final consistency authority.

### Phase 7

- HMAC Signature
- Timestamp validation
- Replay attack defense
- Authentication/authorization hardening

### Phase 8

- Prometheus metrics
- Grafana dashboard
- Structured logging
- `trace_id` / `event_id` / masked `idempotency_key`

### Phase 9

- k6 load tests
- Duplicate storm tests
- p95/p99/RPS/error-rate measurement
- Redis before/after comparison

### Phase 10+

- Failure scenarios
- CI/CD gates
- Deployment safety
- Blog/README/portfolio polish

## 5. Non-Negotiable Domain Rules

- The same `external_event_id` must be applied only once.
- The same `Idempotency-Key` plus the same Body must return the same result.
- The same `Idempotency-Key` plus a different Body must be treated as a conflict.
- `TransactionEvent`, `LedgerEntry`, `Account.balance`, and `IdempotencyRecord` should be handled consistently inside a clear DB transaction boundary whenever possible.
- `LedgerEntry` is the reason/source for balance changes.
- `Account.balance` must be verifiable from accumulated LedgerEntry amounts.
- CANCEL is a compensating transaction, not deletion.
- SETTLED transactions cannot be directly CANCELLED.
- Redis failure must not break final consistency guaranteed by PostgreSQL.
- Do not put business logic in the API layer.
- Repositories must not call `commit`.
- Services must clearly manage or participate in transaction boundaries.
- Domain exceptions and HTTP exceptions must remain separated.
- Do not use `float` for money.
- Current money policy is KRW integer won units.
- Future Decimal/Numeric support requires a separate migration and documentation update.

## 6. Architecture Rules

Backend responsibilities:

- API Router:
  - request/response conversion
  - dependency injection
  - service calls
  - HTTP status mapping
- Schema:
  - Pydantic request/response validation
- Service:
  - business use cases
  - transaction boundary
  - idempotency decisions
  - state transition calls
  - ledger/account orchestration
- Domain:
  - enums
  - state machine
  - pure calculation functions
  - domain exceptions
  - pure logic such as `request_hash`
- Repository:
  - DB reads/writes
  - SQLAlchemy queries
  - `flush`
  - no `commit`
- Models:
  - SQLAlchemy ORM
  - DB constraints
  - indexes

## 7. Coding Rules

- Use Python type hints.
- Follow the existing code style.
- Do not make large arbitrary folder-structure changes.
- When changing an existing public interface, update tests and docs together.
- Manage domain strings with enums whenever practical.
- Prefer timezone-aware `datetime`.
- Do not log a full `idempotency_key`.
- Do not log a full `account_no`.
- Mask personal or identifying values.
- Domain logs should go through the observability `log_event()` helper so masking and trace context are applied consistently.
- Generate `request_hash` using canonical JSON.
- JSON bodies with different key order but the same meaning must produce the same hash.
- Validate status transitions through `TransactionStateMachine`.
- Record status changes in `EventStateHistory`.
- Do not delete `LedgerEntry` rows.
- Failure scenarios must be reproducible by tests.

## 8. Testing Rules

After code changes, run as much of the following as practical.

Basic backend verification:

```bash
cd backend
python -m compileall app tests
pytest
```

Preferred repository-level final check:

```bash
make final-check
```

Additional targeted checks:

```bash
make test-unit
make test-integration
make test-consistency
```

For migration-related changes:

```bash
alembic upgrade head --sql
```

Testing expectations:

- Unit tests should cover pure domain rules and service decisions.
- Integration tests should cover repository behavior and DB constraints.
- Consistency tests should prove duplicate-prevention rules.
- SQLite tests are acceptable for fast regression checks, but PostgreSQL-specific behavior such as JSONB, timestamptz, row locks, and concurrent unique conflicts must be documented and verified with PostgreSQL-based tests when that Phase requires it.

## 9. Documentation Rules

- If behavior changes, update the relevant docs in the same task.
- Do not claim Redis/HMAC/metrics/load-test functionality is implemented before its Phase.
- Keep roadmap status aligned with actual implementation.
- Keep API contract, schema, and tests aligned.
- Keep data model docs aligned with SQLAlchemy models and migrations.
- Keep CANCEL policy aligned with implementation.
- For blog work, edit only the target blog file and directly related references unless the user explicitly requests a broader rewrite.

## 10. Security and Logging Rules

- Never commit secrets.
- Never hardcode production credentials.
- Mask account numbers in responses/logs where appropriate.
- Do not log full Idempotency-Key values.
- HMAC, timestamp validation, replay attack defense, and stronger auth belong to Phase 7 unless explicitly requested.
- If adding logs, prefer structured logs and include request/event context without leaking sensitive identifiers.

## 11. Concurrency and Consistency Rules

- PostgreSQL unique constraints are the final duplicate-defense layer.
- `idempotency_records.idempotency_key` must remain unique.
- `transaction_events.external_event_id` must remain unique.
- `ledger_entries.transaction_event_id` must remain unique.
- Account balance changes and LedgerEntry creation must be atomic.
- Account row locking should use `SELECT FOR UPDATE` where appropriate.
- Redis locks may reduce load, but must never be the only correctness mechanism.
- On concurrent insert conflicts, use rollback plus read-after-conflict strategy where appropriate.
- Document SQLite limitations when row locks or concurrency are not faithfully tested.

## 12. Pull Request Expectations

PR summaries should include:

- Changed files or areas
- Implemented behavior
- Tests added/updated
- Commands run and results
- Phase completion status
- TODOs for the next Phase

Before finalizing a PR, verify:

- The implementation does not exceed the requested Phase.
- Domain rules remain intact.
- Tests pass or skipped tests are explicitly justified.
- Docs and roadmap match the actual state.
