# 18. Performance Troubleshooting Guide

## 1. 목적

이 문서는 성능 저하나 오류율 증가가 발생했을 때 원인을 추적하는 순서를 정의한다.

---

## 2. 기본 판단 순서

성능 문제가 발생하면 다음 순서로 확인한다.

```text
1. p95/p99 latency와 5xx error rate 확인
2. 특정 endpoint 또는 배포 직후 문제인지 확인
3. DB query/connection pool/transaction duration 확인
4. Redis fallback, lock rejected, cache hit/miss 확인
5. duplicate event와 invalid state transition 증가 여부 확인
6. reconciliation failure 확인
7. 최근 Blue-Green 전환 또는 rollback 여부 확인
8. 구조화 로그에서 trace_id/request_id/event_id 기준으로 요청 흐름 추적
```

Phase 9~10에서 확인한 기준은 다음과 같다.
성능 지표가 튀더라도 중복 Ledger/Event가 0건이면 정합성은 유지된 것이다.
반대로 p95가 안정적이어도 duplicate ledger가 1건이라도 발생하면 성능 테스트는 실패로 판단한다.

---

## 3. p95/p99가 증가했을 때

### 확인 지표

- `http_request_duration_seconds`
- `financial_db_transaction_duration_seconds`
- `db_connection_wait_seconds`
- `db_connections_active`
- `redis_command_duration_seconds`

### 가능한 원인

- DB Connection Pool 부족
- Transaction 범위가 너무 큼
- Redis 장애로 DB fallback 증가
- 특정 쿼리 지연
- Lock 경합
- 외부 시스템 중복 재시도 폭주

### 대응

- Slow query 확인
- Transaction 범위 축소
- Pool size 조정
- Redis Cache Hit Ratio 확인
- 중복 요청 폭주 여부 확인

---

## 4. error rate가 증가했을 때

### 확인 지표

- `http_5xx_total`
- `http_4xx_total`
- `financial_events_failed_total`
- `financial_external_auth_failed_total`
- `financial_idempotency_conflict_total`

### 가능한 원인

- DB 연결 실패
- Redis 장애가 fallback으로 처리되지 않음
- HMAC Signature 검증 실패 증가
- 같은 Idempotency-Key로 다른 Body 요청 증가
- 배포 후 응답 스키마 오류

### 대응

- 5xx와 4xx를 분리해서 본다.
- 5xx는 서버/인프라 문제로 추적한다.
- 4xx는 외부 요청 형식, 인증, 충돌 정책 문제로 추적한다.

---

## 5. duplicate event가 증가했을 때

### 확인 지표

- `financial_events_duplicate_total`
- `financial_idempotency_hit_total`
- `financial_idempotency_conflict_total`
- `financial_ledger_entries_created_total`

### 해석

duplicate event 증가 자체는 장애가 아닐 수 있다.
외부 시스템 재시도가 많아지면 duplicate event는 증가할 수 있다.

중요한 것은 duplicate event 증가가 ledger 중복 생성으로 이어졌는지 여부다.

### 성공 기준

`financial_events_duplicate_total`은 증가할 수 있지만, `financial_ledger_entries_created_total`은 동일 `external_event_id` 기준 1건만 생성되어야 한다.

---

## 6. Redis 장애 시

### 확인 지표

- `redis_up`
- `financial_redis_lock_acquire_failed_total`
- `redis_keyspace_hits_total`
- `redis_keyspace_misses_total`
- `financial_db_transaction_duration_seconds`

### 기대 동작

Redis 장애 시 cache hit ratio는 떨어질 수 있다.
DB transaction duration은 증가할 수 있다.

하지만 duplicate processing rate는 0%여야 한다.

---

## 7. 배포 직후 성능 저하

### 확인 지표

- `deployment_version`
- `http_5xx_total`
- p95 latency
- `financial_invalid_state_transition_total`
- `financial_reconciliation_failed_total`
- `db_connections_active`

### 판단 기준

Green 전환 후 5분 이내 5xx rate가 5%를 초과하거나 invalid state transition이 1건 이상 발생하면 rollback한다.

---

## 8. 설계 결론

성능 문제는 단순히 서버 스펙을 높여 해결하지 않는다.

먼저 어떤 계층에서 병목이 발생했는지 메트릭과 로그로 확인하고, 정합성 지표가 깨졌는지 함께 검증한다.
