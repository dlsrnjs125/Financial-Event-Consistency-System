# 16. Performance Measurement Design

## 1. 목적

이 문서는 금융 거래 이벤트 중복 처리 및 정합성 검증 시스템에서 성능을 어떤 기준으로 측정하고, 어떤 설계 판단과 연결할 것인지 정의한다.

이 프로젝트에서 성능 측정의 목적은 단순히 높은 RPS를 만드는 것이 아니다.

핵심은 다음이다.

1. 중복 이벤트가 폭주해도 거래 정합성이 유지되는가?
2. Redis Lock/Cache 도입 전후로 응답시간과 DB 부하가 어떻게 달라지는가?
3. PostgreSQL Transaction과 Unique Constraint가 정합성에는 어떤 이점을 주고, 성능에는 어떤 비용을 만드는가?
4. DB Connection Pool, Redis 장애, 배포 전환 상황에서 p95/p99와 에러율이 어떻게 변하는가?
5. 성능 저하가 발생했을 때 로그, 메트릭, 테스트 결과로 원인을 추적할 수 있는가?

---

## 2. 성능 측정 기본 원칙

성능 측정은 다음 원칙을 따른다.

```text
1. 같은 시나리오를 반복 측정한다.
2. 변경 전/후 수치를 모두 기록한다.
3. 평균 응답시간보다 p95/p99를 우선 확인한다.
4. 응답시간뿐 아니라 정합성 지표를 함께 확인한다.
5. 성능 개선이 정합성을 훼손하지 않았는지 검증한다.
6. 모든 실험 결과는 blog와 docs에 기록한다.
```

---

## 3. 주요 성능 목표

| 지표 | 목표 | 측정 도구 | 의미 |
|------|------|-----------|------|
| p50 latency | 50ms 이하 | k6 | 일반 요청의 중간 응답시간 |
| p95 latency | 300ms 이하 | k6, Prometheus | 대부분 사용자 요청의 상위 지연 |
| p99 latency | 1000ms 이하 | k6, Prometheus | 꼬리 지연, 장애 징후 확인 |
| error rate | 1% 이하 | k6, Prometheus | 실패 요청 비율 |
| duplicate processing rate | 0% | DB query, metrics | 중복 반영 발생 여부 |
| invalid transition success rate | 0% | test, metrics | 잘못된 상태 전이 허용 여부 |
| cache hit ratio | 80% 이상 | Prometheus | Idempotency Cache 효율 |
| DB connection usage | 80% 이하 | Prometheus | Connection Pool 안정성 |
| reconciliation failure | 0건 | metrics | balance와 ledger 불일치 여부 |

---

## 4. 측정 환경 고정

성능 수치는 실행 환경에 따라 달라질 수 있으므로, 각 실험마다 환경을 기록한다.

| 항목 | 기록 값 |
|------|---------|
| 실행 환경 | local / docker compose / EC2 |
| CPU | 예: 2 core |
| Memory | 예: 4GB |
| API worker 수 | 예: 1 |
| DB pool size | 예: 10 |
| Redis 사용 여부 | enabled / disabled |
| 테스트 도구 | k6 |
| 테스트 스크립트 | smoke / peak / duplicate-storm |
| 테스트 날짜 | yyyy-mm-dd |
| git commit hash | commit id |

---

## 5. 비교 실험 목록

### EXP-001. Redis Cache 도입 전/후 비교

목적:

Idempotency 결과를 DB에서 직접 조회하는 방식과 Redis Cache에서 반환하는 방식의 응답시간 차이를 비교한다.

비교 대상:

| 조건 | 설명 |
|------|------|
| A안 | DB에서 IdempotencyRecord 조회 |
| B안 | Redis Cache에서 Idempotency 결과 반환 |

측정 지표:

- p50 latency
- p95 latency
- p99 latency
- DB query count
- cache hit ratio
- error rate
- duplicate processing rate

기대 결과:

Redis Cache 사용 시 중복 요청의 p95 latency와 DB query count가 감소해야 한다.
단, Redis 장애 시에도 duplicate processing rate는 0%여야 한다.

### EXP-002. Redis Lock 도입 전/후 비교

목적:

동일 Idempotency-Key 요청이 동시에 유입될 때 Redis Lock이 DB 진입 요청 수와 충돌 수에 어떤 영향을 주는지 확인한다.

비교 대상:

| 조건 | 설명 |
|------|------|
| A안 | Redis Lock 미사용, DB Unique Constraint만 사용 |
| B안 | Redis Lock + DB Unique Constraint 사용 |

측정 지표:

- `financial_events_duplicate_total`
- `financial_redis_lock_acquire_failed_total`
- DB transaction count
- DB unique violation count
- p95 latency
- p99 latency

설계 판단 기준:

Redis Lock은 DB 부하를 줄이는 데 효과가 있으면 유지한다.
하지만 Redis Lock이 없어도 DB Unique Constraint로 정합성이 유지되어야 한다.

### EXP-003. DB Connection Pool 크기 비교

목적:

DB Connection Pool 크기가 처리량, 응답시간, 에러율에 미치는 영향을 확인한다.

비교 조건:

| 조건 | DB_POOL_SIZE | DB_MAX_OVERFLOW |
|------|--------------|-----------------|
| A안 | 5 | 0 |
| B안 | 10 | 5 |
| C안 | 20 | 10 |

측정 지표:

- p95 latency
- p99 latency
- `http_5xx_total`
- `db_connections_active`
- `db_connection_wait_seconds`
- `financial_db_transaction_duration_seconds`

판단 기준:

Pool 크기가 너무 작으면 503과 connection wait time이 증가한다.
Pool 크기가 너무 크면 DB 자원 사용량이 증가할 수 있다.
따라서 p95/p99와 DB connection usage를 함께 보고 적정 값을 선택한다.

### EXP-004. Transaction 범위 비교

목적:

Transaction 안에 포함되는 로직 범위가 응답시간과 Lock 경합에 미치는 영향을 확인한다.

비교 대상:

| 조건 | 설명 |
|------|------|
| A안 | Transaction 내부에서 검증, 원장 생성, 응답 저장 모두 수행 |
| B안 | 외부 검증은 Transaction 밖에서 수행하고, DB 변경만 Transaction 안에서 수행 |

측정 지표:

- `financial_db_transaction_duration_seconds`
- p95 latency
- p99 latency
- lock wait time
- rollback count

판단 기준:

Transaction은 짧게 유지하되, 정합성에 필요한 DB 변경은 하나의 Transaction으로 묶는다.

### EXP-005. 상태 머신 검증 비용 측정

목적:

상태 머신 검증 로직이 API 응답시간에 주는 영향을 확인한다.

비교 대상:

| 조건 | 설명 |
|------|------|
| A안 | 상태 머신 검증 없음 |
| B안 | 코드 기반 상태 머신 검증 |
| C안 | DB 테이블 기반 상태 전이 검증 |

Phase 1 선택:

```text
코드 기반 상태 머신 검증
```

측정 지표:

- p95 latency
- `financial_invalid_state_transition_total`
- test coverage

판단 기준:

상태 머신 검증의 비용이 크지 않다면 정합성을 위해 유지한다.
DB 테이블 기반 전이는 운영 중 정책 변경이 필요해지는 Phase에서 검토한다.

### EXP-006. Blue-Green 배포 전후 비교

목적:

Green 버전 전환 이후 API 성능과 정합성 지표가 악화되는지 확인한다.

측정 지표:

- `http_5xx_total`
- p95 latency
- p99 latency
- `financial_invalid_state_transition_total`
- `financial_reconciliation_failed_total`
- `financial_events_failed_total`
- `db_connections_active`

판단 기준:

Green 전환 후 5분 이내 5xx rate가 5%를 초과하거나 invalid state transition이 1건 이상 발생하면 rollback한다.

---

## 6. 성능 측정 결과 기록 양식

| 실험 ID | 변경 내용 | p50 | p95 | p99 | error rate | DB conn | cache hit | duplicate rate | 결론 |
|---------|-----------|-----|-----|-----|------------|---------|-----------|----------------|------|
| EXP-001-A | Redis Cache 미사용 | TBD | TBD | TBD | TBD | TBD | TBD | 0% | 기준선 |
| EXP-001-B | Redis Cache 사용 | TBD | TBD | TBD | TBD | TBD | TBD | 0% | 비교 예정 |

---

## 7. 설계 결론

이 프로젝트의 성능 측정은 단순히 빠른 API를 만드는 것이 아니라, 정합성을 유지하면서 어느 지점에서 병목이 발생하는지 확인하기 위한 과정이다.

따라서 모든 성능 실험은 응답시간, 에러율, DB/Redis 지표뿐 아니라 중복 반영률, 잘못된 상태 전이 수, reconciliation 실패 수와 함께 해석한다.
