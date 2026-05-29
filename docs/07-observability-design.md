# 07. Observability Design

## 1. 관측성 설계 목적

이 시스템에서 중요한 것은 단순히 API 서버가 살아 있는지 확인하는 것이 아니다.

금융 이벤트 처리 시스템에서는 다음 질문에 답할 수 있어야 한다.

1. 동일 이벤트가 중복 처리되고 있지 않은가?
2. Idempotency-Key가 정상적으로 동작하고 있는가?
3. 잘못된 상태 전이가 발생하고 있지 않은가?
4. Redis 장애가 API 전체 장애로 번지고 있지 않은가?
5. DB Connection Pool이 고갈되고 있지 않은가?
6. 배포 이후 에러율과 응답시간이 악화되지 않았는가?
7. 특정 거래 이벤트의 처리 흐름을 trace_id로 추적할 수 있는가?

현재 구현 범위의 trace는 `X-Trace-ID`/`X-Request-ID`와 구조화 로그를 연결하는 상관관계 추적이다.
W3C `traceparent`/`tracestate` 전파와 OpenTelemetry SDK 기반 분산 추적은 아직 구현하지 않았으며, 후속 고도화 항목으로 둔다.

---

## 2. 일반 인프라 메트릭과 도메인 메트릭 구분

### 일반 인프라 메트릭

일반적인 서버 상태 확인에 사용한다.

```text
CPU usage
Memory usage
Disk usage
Network I/O
Container restart count
```

### API 메트릭

API 성능과 안정성을 확인한다.

```text
http_requests_total
http_request_duration_seconds
http_requests_failed_total
http_4xx_total
http_5xx_total
```

### 도메인 메트릭

금융 이벤트 정합성을 확인한다.

```text
financial_events_received_total
financial_events_processed_total
financial_events_duplicate_total
financial_events_failed_total
financial_invalid_state_transition_total
financial_idempotency_hit_total
financial_idempotency_conflict_total
financial_ledger_entries_created_total
financial_reconciliation_failed_total
```

### 인프라 의존성 메트릭

Redis와 PostgreSQL 상태를 확인한다.
Phase 8~9 현재 scrape는 FastAPI 애플리케이션 메트릭 중심이며, Redis/PostgreSQL exporter 기반 내부 지표는 후속 보완 항목이다.

```text
financial_redis_lock_acquire_failed_total
financial_db_transaction_duration_seconds
db_connections_active
db_connections_idle
db_connection_wait_seconds
redis_up
redis_keyspace_hits_total
redis_keyspace_misses_total
```

---

## 3. 확정 메트릭 이름

| 메트릭 | 의미 |
|--------|------|
| `financial_events_received_total` | 수신한 금융 이벤트 수 |
| `financial_events_processed_total` | 정상 처리 완료된 이벤트 수 |
| `financial_events_duplicate_total` | 중복 요청으로 판단된 이벤트 수 |
| `financial_events_failed_total` | 처리 실패한 이벤트 수 |
| `financial_invalid_state_transition_total` | 잘못된 상태 전이 차단 수 |
| `financial_idempotency_hit_total` | 기존 Idempotency 결과를 반환한 수 |
| `financial_idempotency_conflict_total` | 같은 Key로 다른 Body가 들어온 수 |
| `financial_ledger_entries_created_total` | 생성된 원장 기록 수 |
| `financial_reconciliation_failed_total` | 잔액과 원장 합계 불일치 수 |
| `financial_redis_lock_acquire_failed_total` | Redis Lock 획득 실패 수 |
| `financial_db_transaction_duration_seconds` | DB Transaction 수행 시간 |
| `financial_external_auth_failed_total` | 외부 시스템 인증 실패 수 |
| `financial_hmac_signature_invalid_total` | HMAC Signature 검증 실패 수 |

---

## 4. trace_id / request_id / event_id 설계

### request_id

개별 HTTP 요청을 식별한다.

요청 1개는 request_id 1개를 가진다.

사용 목적:

- API 요청 로그 추적
- Nginx 로그와 API 로그 연결
- 장애 발생 요청 확인

### trace_id

하나의 거래 처리 흐름을 추적한다.

```text
외부 시스템 요청 -> API 처리 -> Redis 확인 -> DB Transaction -> 응답 반환
```

사용 목적:

- 하나의 거래 이벤트 전체 흐름 추적
- 여러 내부 로그를 하나의 흐름으로 연결

### event_id

시스템 내부에서 생성한 거래 이벤트 식별자다.

사용 목적:

- `transaction_events` 테이블과 로그 연결
- 상태 이력 추적
- 운영자 조회 기준

### external_event_id

외부 금융 시스템에서 전달한 이벤트 식별자다.

사용 목적:

- 외부 시스템과 장애 분석 시 기준 값
- 중복 이벤트 판단 기준

### idempotency_key

재시도 요청과 중복 요청을 식별한다.

사용 목적:

- 동일 요청 재전송 판단
- 기존 응답 반환
- 충돌 요청 감지

---

## 5. 구조화 로그 설계

로그 예시:

```json
{
  "timestamp": "2026-05-27T10:00:00.000+09:00",
  "level": "INFO",
  "service": "financial-event-api",
  "environment": "local",
  "trace_id": "trc-20260527-0001",
  "request_id": "req-20260527-0001",
  "event_id": "evt-0001",
  "external_event_id": "BANK-A-20260527-0001",
  "idempotency_key_masked": "id***0001",
  "client_id": "bank-a",
  "event_type": "DEPOSIT",
  "status_before": "PROCESSING",
  "status_after": "COMPLETED",
  "http_method": "POST",
  "path": "/api/v1/transaction-events",
  "status_code": 200,
  "latency_ms": 132,
  "operation": "transaction_event_process",
  "dependency": "postgres",
  "fallback_used": false,
  "error_type": null,
  "duration_ms": 132,
  "message": "transaction event processed successfully"
}
```

Phase 10 Redis fallback 로그는 동일한 trace/request context를 유지하고 `operation`, `dependency`, `fallback_used`, `error_type`, `duration_ms`를 포함한다.
`account_no`와 `idempotency_key`는 원문을 남기지 않고 masking helper를 통해 `account_no_masked`, `idempotency_key_masked`로 기록한다.

---

## 6. Grafana Dashboard 구성

### Dashboard 1. API Overview

목적: API 성능과 오류율 확인

패널:

- RPS
- p50 latency
- p95 latency
- p99 latency
- 4xx error rate
- 5xx error rate
- Endpoint별 latency

### Dashboard 2. Financial Event Consistency

목적: 거래 이벤트 정합성 상태 확인

패널:

- 수신 이벤트 수
- 처리 완료 이벤트 수
- 중복 이벤트 수
- Idempotency Hit Ratio
- Idempotency Conflict 수
- 잘못된 상태 전이 수
- 원장 기록 생성 수
- Reconciliation 실패 수

### Dashboard 3. PostgreSQL

목적: DB 병목과 정합성 위험 감지

현재 Phase 8~9 구현에는 PostgreSQL exporter가 포함되지 않는다.
아래 패널은 Phase 10~12에서 exporter 또는 SQLAlchemy pool gauge를 추가한 뒤 활성화한다.

패널:

- Active Connections
- Idle Connections
- Connection Pool Usage
- Transaction Duration
- Lock Count
- Deadlock Count
- Rollback Count
- Slow Query Count

### Dashboard 4. Redis

목적: Redis Lock/Cache 상태 확인

현재 Phase 8~9 구현에는 Redis exporter가 포함되지 않는다.
애플리케이션에서 노출하는 Redis lock/cache 도메인 메트릭을 우선 사용하고, Redis 서버 내부 지표는 후속 단계에서 추가한다.

패널:

- Redis Up
- Connected Clients
- Cache Hit Ratio
- Cache Miss Ratio
- Memory Usage
- Lock Acquire Failed Count
- Command Latency

### Dashboard 5. Deployment Monitoring

목적: 배포 전후 안정성 비교

패널:

- Blue/Green 버전별 요청 수
- 배포 이후 5xx error rate
- 배포 이후 p95 latency
- Invalid State Transition 증가 여부
- Duplicate Event 증가 여부
- DB Connection 증가 여부
- Rollback 발생 여부

---

## 7. Alert Rule 기준

| Alert | 조건 | 심각도 |
|-------|------|--------|
| APIHighErrorRate | 5xx rate > 5% for 3m | Critical |
| APILatencyHigh | p95 > 1s for 5m | Warning |
| RedisDown | redis_up == 0 for 1m | Critical |
| DBConnectionPoolHigh | pool usage > 85% for 5m | Warning |
| InvalidStateTransitionDetected | invalid transition > 0 | Critical |
| IdempotencyConflictSpike | conflict > 10/min | Warning |
| ReconciliationFailed | reconciliation_failed_total > 0 | Critical |
| DuplicateEventSpike | duplicate event rate > 30% for 5m | Warning |
| DBTransactionSlow | transaction p95 > 500ms for 5m | Warning |

---

## 8. 설계 결론

이 프로젝트의 관측성은 서버 리소스 사용량을 보는 수준에 머무르지 않는다.

핵심은 금융 이벤트가 중복 없이 처리되고 있는지, 잘못된 상태 전이가 발생하지 않는지, Redis나 DB 장애가 정합성 문제로 이어지지 않는지를 확인하는 것이다.

따라서 일반 인프라 메트릭과 함께 도메인 메트릭을 직접 정의하고, 로그에는 trace_id, request_id, event_id, external_event_id, idempotency_key를 포함한다.
