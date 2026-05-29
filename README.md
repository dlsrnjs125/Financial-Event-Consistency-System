# Financial Event Consistency System

> 외부 금융 거래 이벤트의 중복 처리, 순서 꼬임, 재시도 문제를 **Idempotency Key, PostgreSQL Transaction, Redis, 상태 머신, 모니터링**으로 검증하는 백엔드/DevOps 프로젝트

[![CI](https://github.com/dlsrnjs125/Financial-Event-Consistency-System/actions/workflows/ci.yml/badge.svg)](https://github.com/dlsrnjs125/Financial-Event-Consistency-System/actions)

---

## 🎯 프로젝트 목표

금융 시스템에서 가장 중요한 것은 **빠른 응답이 아니라, 중복·재시도·장애 상황에서도 거래 결과가 한 번만 정확하게 반영되는 것**입니다.

이 프로젝트는 다음 6가지를 검증합니다:

1. ✅ **동일 이벤트는 여러 번 들어와도 한 번만 처리**
2. ✅ **동일 Idempotency Key 요청은 항상 같은 결과를 반환**
3. ✅ **잘못된 상태 전이는 차단**
4. ✅ **Redis 장애가 발생해도 PostgreSQL 기준 최종 정합성 유지**
5. ✅ **로컬 검증 명령으로 정합성 회귀를 재현 가능하게 확인**
6. ✅ **Blue-Green 배포와 Rollback 흐름을 Docker Compose로 재현**

Phase 9 측정에서는 Redis 장애 상황에서도 PostgreSQL 기준 중복 반영은 0건이었다.
Phase 10에서는 Redis Down duplicate storm에서 확인된 일부 5xx를 보완하기 위해 Redis fallback, DB unique conflict retry, 장애 재현 명령을 추가했다.
Phase 11에서는 GitHub Actions 기반 배포 Gate를 고도화해 PR 병합 전 정합성, 보안 로그, secret scan, migration, Docker build를 자동 검증한다.
Phase 12에서는 Green 환경 검증 후 Nginx upstream을 전환하고, 이상 발생 시 Blue로 rollback하는 배포 시뮬레이션을 구현했다.

---

## 📋 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    외부 금융 시스템 (은행, 결제사 등)         │
└────────────────┬────────────────────────────────────────────┘
                 │ Webhook / API 호출
                 ↓
        ┌────────────────────┐
        │  Nginx             │ (Reverse Proxy, Rate Limit, Blue-Green)
        └────────┬───────────┘
                 │
         ┌───────┴────────┐
         ↓                ↓
    ┌─────────┐      ┌─────────┐
    │ API     │      │ API     │ (Blue-Green Deploy)
    │ Server  │      │ Server  │
    └────┬────┘      └────┬────┘
         │                │
         └────────┬───────┘
                  │
         ┌────────┼───────────┐
         ↓        ↓           ↓
    ┌──────┐  ┌──────┐   ┌─────────┐
    │Redis │  │ PgSQL│   │Prometheus│
    │      │  │      │   │ Grafana  │
    └──────┘  └──────┘   └─────────┘
```

### 구성요소별 역할

| 구성요소 | 역할 | 특징 |
|---------|-----|------|
| **Nginx** | Reverse Proxy, Rate Limit, Blue-Green 트래픽 전환 | upstream snippet 교체로 전환 재현 |
| **API Server** | 이벤트 수신, Idempotency 검증, 상태 전이 처리 | 비즈니스 로직 |
| **Redis** | 중복 요청 완화, Lock, Cache | 성능 최적화 (선택사항) |
| **PostgreSQL** | 최종 정합성 저장소 | 진실의 소스 |
| **Prometheus** | 메트릭 수집 | 모니터링 데이터 |
| **Grafana** | 대시보드 시각화 | 실시간 관측 |

---

## 🚀 빠른 시작

### 요구사항
- Docker & Docker Compose
- Python 3.10+
- PostgreSQL 15
- Redis 7

### 설치 및 실행

```bash
# 1. 저장소 클론
git clone https://github.com/dlsrnjs125/Financial-Event-Consistency-System.git
cd Financial-Event-Consistency-System

# 2. 환경 설정
cp .env.example .env

# 3. 로컬 환경 확인
make local-check

# 4. FastAPI 개발 서버 실행
make dev

# 5. API 확인
make health
```

Docker Compose 기반 전체 로컬 스택은 다음 명령으로 실행한다.

```bash
make local-bg
make local-status
make local-logs
make local-stop
```

### Makefile 주요 명령

```bash
make help          # 사용 가능한 명령 확인
make local-check   # 로컬 개발 환경 확인
make dev           # FastAPI reload 서버 실행
make check         # format-check, lint, test 실행
make format        # 코드 자동 포맷
make final-check   # 코드 수정 없이 PR 전 최종 검증
make ci-local      # Phase 11 빠른 로컬 Gate 검증
make local-bg      # Docker Compose 스택 백그라운드 실행
make local-stop    # Docker Compose 스택 중지
make deploy-status # Blue/Green/Nginx 배포 상태 확인
make deploy-green  # Green 컨테이너 실행과 사전 검증
make deploy-blue-green # Green 검증 후 Nginx upstream 전환
make deploy-rollback   # Nginx upstream을 Blue로 rollback
make deploy-smoke      # lightweight 배포 smoke test
make deploy-verify     # PostgreSQL 정합성 검증
make phase12-check     # Phase 12 Blue-Green/rollback 통합 검증
```

### 주요 엔드포인트

```
GET /health        서버 상태
GET /ready         PostgreSQL readiness와 Redis degraded 상태 확인
GET /metrics       Prometheus 메트릭
POST /api/v1/transaction-events
GET /api/v1/transaction-events/{event_id}
GET /api/v1/accounts/{account_no}/balance
```

현재 구현 상태는 Phase 12까지 완료된 상태이며, 금융 이벤트 정합성 검증, Redis 장애 fallback, CI/CD Deployment Gate, Blue-Green 배포 및 Rollback 시뮬레이션까지 구현했다.

핵심 거래 처리:

- `POST /api/v1/transaction-events`로 거래 이벤트를 수신한다.
- Idempotency Key와 canonical request hash로 동일 요청 재전송과 충돌 요청을 구분한다.
- TransactionEvent, LedgerEntry, Account.balance, IdempotencyRecord를 PostgreSQL transaction 안에서 일관되게 처리한다.
- LedgerEntry가 balance 변경의 근거이며, 동일 `external_event_id`와 동일 Ledger 반영은 PostgreSQL unique constraint로 최종 방어한다.
- 금액은 현재 KRW 정수 원 단위로 처리한다.

Redis와 장애 처리:

- Redis는 completed idempotency response cache와 동일 key 중복 요청 완화를 위한 lock/cache 계층이다.
- Redis는 최종 정합성 저장소가 아니며, PostgreSQL Unique Constraint와 DB Transaction이 Source of Truth다.
- Redis connection error 또는 timeout이 발생하면 Redis lock/cache를 생략하고 PostgreSQL 기준 degraded mode로 처리한다.
- Redis Down duplicate storm에서 DB unique conflict가 발생하면 rollback 후 한 번 재시도해 기존 idempotency/event 결과를 읽는다.
- PostgreSQL 장애는 degraded mode 대상이 아니며 `/ready` 실패와 5xx/503 계열 오류로 구분한다.

보안과 관측성:

- HMAC 인증은 `POST /api/v1/transaction-events`에 적용된다.
- 모든 HTTP 응답에는 `X-Trace-ID`, `X-Request-ID`가 포함된다.
- 구조화 로그는 trace/request context, bounded operation/dependency 필드, masked `idempotency_key`와 masked `account_no`를 사용한다.
- Prometheus custom metric으로 HTTP, transaction, idempotency, Redis fallback, readiness 상태를 확인한다.

향후 고도화 후보:

- 조회 API의 외부 공개 여부와 권한 모델
- W3C `traceparent`/`tracestate` 전파
- OpenTelemetry SDK 기반 분산 추적
- Redis/PostgreSQL exporter 기반 인프라 내부 metric
- 운영 환경 기준 alert threshold 재조정

위 항목은 본 프로젝트의 핵심 구현 범위에서는 제외하고, 향후 운영 고도화 과제로 남긴다.

HMAC Header 예시:

```http
X-Client-Id: bank-a
X-Timestamp: 2026-05-27T10:00:00+09:00
X-Signature: <hmac-sha256-hex-digest>
Idempotency-Key: idem-20260527-0001
```

Signature base string은 `METHOD\nPATH\nTIMESTAMP\nBODY_HASH` 형식이며, 반드시 LF newline으로 구분한다.
`X-Signature`는 64-character hex digest만 지원하고 `sha256=` prefix 형식은 지원하지 않는다.
로컬/테스트용 client secret은 `.env.example`의 `EXTERNAL_CLIENT_SECRETS` 더미 값을 참고한다.
`HMAC_ENABLED=false`는 local/test 편의용이며, 운영 환경에서는 활성화해야 한다.

`/metrics`에서는 다음 custom metric을 확인할 수 있다.

```text
financial_http_requests_total
financial_transaction_events_total
financial_idempotency_decisions_total
financial_redis_lock_acquired_total
financial_idempotency_cache_hit_total
financial_redis_operation_total
financial_redis_operation_failed_total
financial_redis_fallback_total
financial_db_transaction_retry_total
financial_readiness_dependency_status
financial_hmac_auth_failures_total
financial_invalid_state_transition_total
financial_reconciliation_failures_total
```

Grafana dashboard와 alert rule은 로컬 검증용 초안이다.
Phase 9/10에서 k6 측정값과 Redis fallback 결과를 기록했지만, 운영 임계값은 장시간 운영 데이터와 exporter 보강 후 조정한다.
`docker compose up -d` 실행 후 `http://localhost:8000/metrics`에서 API metric을 확인하고,
`http://localhost:9090`에서 Prometheus target 상태를 확인하며,
`http://localhost:3000`에서 Grafana dashboard 초안을 확인할 수 있다.

---

## 📚 기술 블로그 시리즈

이 프로젝트의 설계 과정과 구현 방식을 12편의 기술 블로그로 설명합니다.

1. [왜 금융 이벤트 처리에서 중복 처리가 중요한가?](./blog/01-why-financial-event-consistency.md) - retry, timeout, 중복 수신이 잔액 불일치로 이어지는 문제를 정의한다.
2. [도메인 모델링과 상태 머신 설계](./blog/02-domain-model-and-state-machine.md) - TransactionEvent, LedgerEntry, Account, IdempotencyRecord의 책임을 분리한다.
3. [Idempotency Key로 중복 요청을 방어하는 방법](./blog/03-idempotency-key-design.md) - 같은 key/body 재요청과 같은 key/different body 충돌을 구분한다.
4. [PostgreSQL Transaction과 Unique Constraint로 정합성 보장하기](./blog/04-postgresql-transaction-unique-constraint.md) - DB transaction과 unique constraint를 최종 방어선으로 둔다.
5. [Redis Lock/Cache를 어디까지 믿어야 할까?](./blog/05-redis-lock-cache-fallback.md) - Redis를 최적화 계층으로 제한하고 장애 시 fallback한다.
6. [잘못된 상태 전이를 막는 테스트 전략](./blog/06-state-transition-test-strategy.md) - 상태 전이표와 회귀 테스트로 잘못된 흐름을 차단한다.
7. [k6로 중복 이벤트 폭주 상황 재현하기](./blog/07-k6-duplicate-storm-performance-test.md) - duplicate storm에서 p95/p99와 중복 반영 0건을 함께 본다.
8. [Prometheus/Grafana로 거래 이벤트 처리 상태 관측하기](./blog/08-prometheus-grafana-observability.md) - metric과 구조화 로그의 역할을 분리한다.
9. [Docker Compose 기반 장애 재현 환경 만들기](./blog/09-docker-compose-failure-simulation.md) - Redis/DB/API 장애를 명령으로 반복 재현한다.
10. [CI/CD에서 정합성 테스트를 배포 Gate로 사용하는 방법](./blog/10-ci-cd-consistency-deployment-gate.md) - 빠른 consistency gate와 heavy k6 test를 분리한다.
11. [Blue-Green 배포와 Rollback 시뮬레이션](./blog/11-blue-green-rollback-simulation.md) - Green 검증, Nginx 전환, rollback 복구를 명령으로 고정한다.
12. [프로젝트 회고: 금융 이벤트 정합성과 운영 안정성을 어떻게 설계했는가](./blog/12-project-retrospective.md) - 설계 판단, 트러블슈팅, AI 활용 검증 과정을 정리한다.

---

## 📊 검증 기준

### 정합성 규칙

| 규칙 | 검증 방법 | 목표 |
|-----|---------|------|
| 동일 이벤트는 한 번만 처리 | 100개 동시 요청 → 1개만 반영 | ✅ 0% 중복 |
| Idempotency Key는 같은 응답 반영 | 재전송 → 첫 결과 반환 | ✅ 100% 일치 |
| 다른 Body는 409 Conflict | 다른 금액 + 같은 Key | ✅ 즉시 거부 |
| 잘못된 상태 전이 차단 | COMPLETED → PROCESSING 시도 | ✅ 0% 성공 |
| Redis 장애 시 degraded 처리 | Redis Down duplicate storm + DB 검증 SQL | ✅ 중복 반영 0건, Redis 장애 단독 5xx 확산 방지 |

### 성능 지표

| 지표 | 메트릭 이름 | 목표 | 측정 |
|------|-------------|------|------|
| p50 응답시간 | `financial_http_request_duration_seconds` p50 | 50ms 이하 | k6, Prometheus |
| p95 응답시간 | `financial_http_request_duration_seconds` p95 | 300ms 이하 | k6, Prometheus |
| p99 응답시간 | `financial_http_request_duration_seconds` p99 | 1000ms 이하 | k6, Prometheus |
| 에러율 | `http_req_failed`, `financial_http_errors_total` | 1% 이하 | k6, Prometheus |
| 캐시 히트율 | `financial_idempotency_cache_hit_total` / miss | 80% 이상 | Prometheus |

### 성능 측정과 설계 비교 계획

이 프로젝트에서는 단순히 최종 성능 수치만 기록하지 않고, 주요 설계 선택 전후의 수치를 비교한다.

| 실험 | 비교 대상 | 주요 지표 | 목적 |
|------|-----------|-----------|------|
| Redis Cache 비교 | DB 직접 조회 vs Redis Cache | p95, p99, DB query count, cache hit ratio | Idempotency 응답 최적화 효과 확인 |
| Redis Lock 비교 | DB Unique only vs Redis Lock + DB Unique | DB transaction count, duplicate rate, p95 | 중복 요청 폭주 완화 효과 확인 |
| DB Pool 비교 | pool size 5/10/20 | p95, p99, 503 rate, connection wait | 적정 pool size 탐색 |
| Transaction 범위 비교 | 긴 transaction vs 짧은 transaction | transaction duration, lock wait, p99 | Lock 경합 감소 |
| 배포 전후 비교 | Blue vs Green | 5xx, p95, invalid transition, reconciliation failure | 배포 안정성 검증 |

성능 개선은 응답시간만으로 판단하지 않는다.

중복 반영률, 잘못된 상태 전이 수, reconciliation 실패 수가 0을 유지하는지 함께 확인한다.

---

## 🧪 테스트 전략

### Unit Test
```bash
make test-unit
```

Idempotency 관련 단위 테스트만 실행하려면 다음 명령을 사용한다.

```bash
pytest backend/tests/unit/test_idempotency_hash.py
pytest backend/tests/unit/test_idempotency_service.py
pytest backend/tests/unit/test_idempotency_dependency.py
```

Transaction/Ledger 관련 테스트만 실행하려면 다음 명령을 사용한다.

```bash
pytest backend/tests/unit/test_ledger_service.py
pytest backend/tests/unit/test_transaction_event_service.py
pytest backend/tests/integration/test_transaction_event_processing.py
pytest backend/tests/integration/test_transaction_event_api.py
```

HMAC 보안 관련 테스트만 실행하려면 다음 명령을 사용한다.

```bash
pytest backend/tests/unit/test_hmac_signature.py
pytest backend/tests/unit/test_timestamp_validation.py
pytest backend/tests/unit/test_client_secret_provider.py
pytest backend/tests/unit/test_masking.py
pytest backend/tests/integration/test_transaction_event_security.py
```

Observability 관련 테스트만 실행하려면 다음 명령을 사용한다.

```bash
pytest backend/tests/unit/test_observability_context.py
pytest backend/tests/unit/test_metrics_helpers.py
pytest backend/tests/unit/test_structured_logging.py
pytest backend/tests/integration/test_observability_metrics.py
pytest backend/tests/integration/test_request_context_middleware.py
```

### Integration Test
```bash
make test-integration
```

현재 Repository/Transaction integration test는 빠른 회귀 검증을 위해 SQLite in-memory 기반으로 실행한다.
PostgreSQL 고유 동작(JSONB, timestamptz, SELECT FOR UPDATE, concurrent unique conflict)은 Phase 6 이후 Docker Compose 기반 integration test에서 별도로 검증한다.

### Consistency Test (필수!)
```bash
make test-consistency
```

### 전체 검증
```bash
make check
```

### 개발 마무리 점검
```bash
make final-check
make ci-local
```

코드 자동 정리는 `make format`으로 수행한다.
모든 개발 작업은 PR 생성 전 `make final-check`로 코드 수정 없이 formatter drift, 린트, Python 컴파일, 전체 테스트, 민감 로그 검사를 확인한다.
GitHub Actions와 유사한 순서로 빠르게 확인하려면 `make ci-local`을 실행한다.
`make ci-local`은 빠른 feedback을 위해 unit test 중심으로 실행하고, PostgreSQL/Redis service container 기반 consistency/migration Gate는 GitHub Actions에서 최종 확인한다.

### 부하 테스트 (k6)

현재 k6 스크립트는 HMAC이 켜진 상태에서 실행하는 것을 원칙으로 한다.
로컬 Docker Compose 스택은 Nginx를 `http://localhost:8080`으로 노출하고,
테스트용 client secret은 `.env.example`의 더미 값과 같은 `bank-a:change-me-secret`을 사용한다.
기본 Nginx 설정은 운영형 rate limit을 유지한다.
부하 실험에서는 `docker-compose.perf.yml`과 `infra/nginx/nginx.perf.conf`를 사용해 Nginx가 API/Redis/PostgreSQL 병목을 가리지 않도록 분리한다.

```bash
# macOS 예시
brew install k6

# 또는 Docker 기반 실행 예시
docker run --rm \
  -v "$PWD:/work" \
  -w /work \
  -e BASE_URL=http://host.docker.internal:8080 \
  -e CLIENT_ID=bank-a \
  -e CLIENT_SECRET=change-me-secret \
  grafana/k6 run tests/k6/smoke-test.js

# Linux Docker 예시
docker run --rm --network host \
  -v "$PWD:/work" \
  -w /work \
  -e BASE_URL=http://localhost:8080 \
  -e CLIENT_ID=bank-a \
  -e CLIENT_SECRET=change-me-secret \
  grafana/k6 run tests/k6/smoke-test.js
```

권장 실행 순서:

```bash
make local-perf-bg
make phase9-check
make phase9-measure
```

Redis Down 시나리오는 Phase 9에서 최초 측정했고, Phase 10에서 장애 재현 명령과 fallback hardening을 추가했다.

```bash
make local-perf-bg
make phase9-failure-experiment
```

## Phase 10 - Failure Recovery & Redis Fallback Hardening

Phase 10에서는 Phase 9 성능 측정에서 확인된 Redis Down duplicate storm 상황의 일부 5xx 문제를 보완했다.
Redis를 최종 정합성 저장소가 아닌 중복 요청 완화 및 성능 최적화 계층으로 정의하고, Redis 장애 시 PostgreSQL transaction, unique constraint, idempotency record를 기준으로 degraded mode 처리를 수행하도록 개선했다.

Redis 장애 fallback 정책:

| 상황 | 처리 정책 |
|------|-----------|
| Redis lock/cache 정상 | Redis lock과 completed response cache로 duplicate storm DB 진입을 완화 |
| Redis connection error/timeout | warning log와 metric 기록 후 DB transaction 기준 처리 |
| Redis lock 획득 실패 | Redis 장애가 아니라 동일 key 처리 중으로 보고 `rejected/lock_not_acquired` metric과 202 응답 유지 |
| PostgreSQL unique conflict | rollback 후 1회 재시도해 기존 idempotency/event 결과 조회 |
| PostgreSQL 장애 | Source of Truth 장애이므로 `/ready` 실패 및 5xx/503 계열로 구분 |

`/ready` 정책은 PostgreSQL을 hard dependency로, Redis를 degraded dependency로 분리한다.
PostgreSQL이 정상이면 Redis 장애 중에도 `/ready`는 200 OK와 `mode="degraded"`를 반환해 트래픽 대상에서 제외되지 않도록 한다.
Redis 장애 상태는 response body와 `financial_readiness_dependency_status{dependency="redis"}` metric으로 확인한다.

장애 재현 명령:

```bash
make failure-status
make failure-redis-down
make failure-redis-up
make failure-redis-logs
make failure-api-restart
make failure-db-down
make failure-db-up
```

Redis Down duplicate storm 실행:

```bash
make local-perf-bg
make failure-redis-down
make k6-redis-down-duplicate-storm
make k6-verify
make failure-redis-up
```

자동 복구 trap을 포함한 단일 검증 명령:

```bash
make phase10-redis-down-check
```

검증 기준:

| 항목 | 기준 |
|------|------|
| PostgreSQL 최종 정합성 | `make k6-verify`에서 중복 Ledger/Event 0건 |
| Redis 장애 단독 | 가능한 한 API 5xx로 확산하지 않고 DB fallback |
| PostgreSQL 장애 | Redis fallback 대상이 아니며 readiness 실패 |
| k6 허용 응답 | 200, 201, 202, 409 |
| 5xx 목표 | `server_error_rate < 0.01` |

2026-05-29 KST 로컬 검증 결과:

| Scenario | Requests | p95 | p99 | 5xx | Duplicate Ledger/Event | Result |
|----------|---------:|----:|----:|----:|------------------------:|--------|
| Redis Down duplicate storm | 5013 | 651.15ms | 2.28s | 0 | 0 / 0 | PASS |

`http_req_failed`는 409 Conflict를 실패 응답으로 집계할 수 있으므로, Phase 10 Redis Down storm에서는 `unexpected_response_rate`, `server_error_rate`, PostgreSQL 중복 검증 결과를 함께 본다.

Redis 장애 시 포기한 것은 cache hit 기반 빠른 replay, Redis lock 기반 DB 부하 완화, 낮은 p95/p99 latency다.
대신 PostgreSQL unique constraint와 idempotency record를 최종 방어선으로 사용하고, DB conflict retry와 사후 검증 SQL로 중복 반영 0건을 확인한다.

모니터링 확인 포인트:

```text
financial_redis_operation_total
financial_redis_operation_failed_total
financial_redis_fallback_total
financial_idempotency_duplicate_total
financial_transaction_event_processed_total
financial_transaction_event_failed_total
financial_transaction_event_conflict_total
financial_db_transaction_retry_total
financial_readiness_dependency_status
```

로그 추적은 `trace_id`, `request_id`, masked `idempotency_key`, masked `account_no`, `operation`, `dependency`, `fallback_used`, `error_type`, `duration_ms` 필드를 기준으로 한다.
상세 Failure Mode 명세는 [Phase 10 Failure Recovery](./docs/phase-10-failure-recovery.md)에 기록한다.

Redis Cache/Lock과 DB Pool 비교 실험은 다음 타겟으로 조건을 바꿔 실행한다.

```bash
make perf-cache-off
make perf-cache-on
make perf-lock-off
make perf-lock-on
make perf-db-pool-5
make perf-db-pool-10
make perf-db-pool-20
```

환경변수로 대상 URL과 HMAC client를 바꿀 수 있다.
운영용 secret은 저장소에 기록하지 않고 실행 환경에서 주입한다.

```bash
BASE_URL=http://localhost:8080 \
CLIENT_ID=bank-a \
CLIENT_SECRET=change-me-secret \
ACCOUNT_NO=ACC-001 \
make k6-smoke
```

직접 실행할 수도 있다.

```bash
BASE_URL=http://localhost:8080 CLIENT_ID=bank-a CLIENT_SECRET=change-me-secret k6 run tests/k6/smoke-test.js
BASE_URL=http://localhost:8080 CLIENT_ID=bank-a CLIENT_SECRET=change-me-secret k6 run tests/k6/normal-load.js
BASE_URL=http://localhost:8080 CLIENT_ID=bank-a CLIENT_SECRET=change-me-secret k6 run tests/k6/peak-load.js
BASE_URL=http://localhost:8080 CLIENT_ID=bank-a CLIENT_SECRET=change-me-secret k6 run tests/k6/duplicate-storm.js
BASE_URL=http://localhost:8080 CLIENT_ID=bank-a CLIENT_SECRET=change-me-secret k6 run tests/k6/redis-down-test.js
```

확인해야 할 값:

| 구분 | 확인 지표 |
|------|-----------|
| k6 | p50, p95, p99, RPS, `http_req_failed`, `unexpected_response_rate`, `server_error_rate` |
| Prometheus | `financial_http_request_duration_seconds`, `financial_http_errors_total`, `financial_transaction_processing_duration_seconds` |
| Idempotency | `financial_idempotency_decisions_total`, `financial_idempotency_conflict_total`, `financial_idempotency_processing_total` |
| Redis | `financial_redis_lock_acquired_total`, `financial_redis_lock_rejected_total`, `financial_idempotency_cache_hit_total`, `financial_redis_unavailable_total` |
| 정합성 | 동일 `external_event_id`의 Ledger 중복 생성 0건 |

`unexpected_response_rate`는 HTTP 응답 정책 위반율이며 실제 중복 반영률이 아니다.
실제 duplicate processing rate는 `make k6-verify`로 PostgreSQL 검증 쿼리를 실행해 판단한다.
테스트 후 Prometheus/Grafana 지표와 `make k6-verify` 결과를 함께 확인하고,
Phase 9 성능 비교 결과는 [Phase 9 Performance Results](./docs/performance/phase-9-results.md)에 기록되어 있고, Redis Down fallback 보완 결과는 [Phase 10 Failure Recovery](./docs/phase-10-failure-recovery.md)에 기록되어 있다.
CI/CD gate 고도화 결과는 [Phase 11 CI/CD Gate](./docs/phase-11-ci-cd-gate.md)에 기록되어 있다.
`security-log-check`는 logger 직접 호출과 `log_event()` 구조화 로그에서 `account_no`, `raw_body`, `signature`, `secret`, `idempotency_key`, `password`, `token` 같은 민감 필드가 raw keyword로 들어가는 패턴을 찾는 보안 점검 타겟이다.
Phase 11부터 `security-log-check`는 `make final-check`와 GitHub Actions 필수 Gate에 포함된다.

---

## 🔄 CI/CD Deployment Gate

Phase 11에서는 기존 `.github/workflows/ci.yml`을 금융 이벤트 정합성 배포 Gate로 고도화했다.
PR이 `main` 또는 `develop`에 병합되기 전 format/lint, unit test, PostgreSQL+Redis consistency test, PostgreSQL migration test, security-log-check, secret scan, Docker build를 통과해야 한다.

GitHub Actions job 구성:

| Gate | CI Job | Purpose |
|------|--------|---------|
| Format/Lint | `lint` | `black`, `isort`, `flake8`, `ruff` 기반 코드 품질 검증 |
| Unit Test | `unit-tests` | 도메인/서비스 단위 테스트와 coverage xml 생성 |
| Consistency Test | `consistency-tests` | PostgreSQL + Redis service container에서 consistency, idempotency, 상태 전이 회귀 검증 |
| Migration Test | `migration-tests` | PostgreSQL에서 `alembic upgrade head`, revision, unique constraint smoke check |
| Security Log Check | `security-log-check` | 운영 코드 구조화 로그의 raw 민감 필드 노출 방지 |
| Secret Scan | `secret-scan` | TruffleHog 기반 repository credential 유출 검사 |
| Docker Build | `docker-build` | `backend/Dockerfile` image build와 inspect |
| Gate Summary | `gate-check` | 모든 필수 job 결과를 종합하고 실패 job을 명확히 출력 |

로컬 명령과 CI job 대응:

| Local Command | CI Job | Purpose |
|---------------|--------|---------|
| `make format-check` | `lint` | formatter drift 확인 |
| `make lint` | `lint` | 정적 분석 |
| `make test-unit` | `unit-tests` | 단위 테스트 |
| `make test-consistency` | `consistency-tests` | 정합성 회귀 검증 |
| `alembic upgrade head` + `make migration-smoke` | `migration-tests` | PostgreSQL migration과 unique constraint smoke 검증 |
| `make security-log-check` | `security-log-check` | 민감 로그 검사 |
| `docker build -t financial-events:test ./backend` | `docker-build` | 배포 이미지 검증 |
| `make ci-local` | local equivalent | format/lint/unit/security-log/compile 빠른 로컬 Gate |

Gate 흐름:

```
[Pull Request]
    ↓
[Format / Lint]
    ↓
[Unit Test]
    ↓
[Consistency Test]
    ↓
[Migration Test]
    ↓
[Security Log Check]
    ↓
[Secret Scan]
    ↓
[Docker Build]
    ↓
[Deployment Gate Summary]
    ↓
merge 허용 또는 차단
```

k6 smoke/normal/peak/duplicate/Redis Down duplicate storm은 PR 필수 Gate가 아니다.
부하 테스트는 실행 시간이 길고 환경 편차가 크기 때문에 수동 local gate, 릴리즈 전 성능 Gate, 또는 nightly workflow 후보로 분리한다.
PR Gate에서는 빠른 consistency test와 idempotency regression test로 중복 반영 0건, 상태 전이 차단, Redis fallback 회귀를 검증한다.

`security-log-check`와 `secret-scan`은 역할이 다르다.
`security-log-check`는 운영 코드의 구조화 로그에서 raw idempotency key, account number, signature, secret 같은 민감 필드를 직접 남기는 패턴을 막는다.
`secret-scan`은 repository에 실제 credential이 들어갔는지 검사한다.
Secret scan action은 CI 재현성을 위해 floating ref(`@main`)나 존재하지 않는 major tag가 아니라 TruffleHog `v3.95.3` commit SHA로 고정한다.
TruffleHog는 PR Gate 안정성을 위해 `--only-verified`를 사용한다. 오탐은 줄어들지만, unverified secret-like pattern 탐지는 별도 강화 후보로 남긴다.

---

## Phase 12 - Blue-Green Deployment & Rollback Simulation

Phase 12에서는 Phase 11 CI Gate를 통과한 변경을 Green 환경에서 먼저 검증하고, Nginx upstream을 Blue에서 Green으로 전환한 뒤, 이상 발생 시 Blue로 rollback하는 절차를 Docker Compose로 재현한다.

배포 흐름:

```text
CI Gate 통과
  -> Green 컨테이너 실행
  -> Green /health, /ready 확인
  -> deployment smoke, migration-smoke 확인
  -> nginx -t
  -> upstream-active.conf를 Green template으로 교체
  -> nginx reload, 실패 시 이전 snippet과 active color 복구
  -> Nginx 기준 smoke/readiness 확인
  -> 이상 시 Blue rollback
```

명령:

```bash
make local-bg
make deploy-status
make deploy-green
make deploy-blue-green
make deploy-smoke
make deploy-verify
make deploy-rollback
make phase12-check
```

Rollback 흐름:

```bash
ROLLBACK_REASON="post-switch smoke failed" make deploy-rollback
make deploy-smoke
make deploy-verify
```

검증 기준:

| 항목 | 기준 |
|------|------|
| Green health/readiness | `/health` 200, `/ready` 200 |
| Redis degraded | PostgreSQL이 정상이라면 허용 |
| PostgreSQL failure | `/ready` 실패, 전환 차단 또는 rollback 판단 |
| Nginx config | 전환 전후 `nginx -t` 성공 |
| Smoke | HMAC POST, idempotency replay, validation failure 확인 |
| 정합성 | `make deploy-verify`에서 중복 Ledger/Event 0건 |

Compose orchestration에서도 Redis는 hard dependency로 차단하지 않는다.
`api-blue`와 `api-green`은 PostgreSQL만 `service_healthy`로 기다리고, Redis는 `service_started`로 두어 Redis unhealthy 상태에서도 애플리케이션의 `/ready mode="degraded"` 정책과 충돌하지 않게 한다.
Green은 host에서 `8001`로 확인하지만 컨테이너 내부 listen port는 Blue와 같은 `8000`이며, Nginx upstream도 `api-green:8000`을 바라본다.

Nginx 전환은 `nginx.conf` 전체를 수정하지 않고 `infra/nginx/conf.d/upstream-active.conf` snippet만 template에서 교체한다.
Green 검증 실패 시 upstream을 전환하지 않으며, 전환 후 smoke/readiness 실패 시 `AUTO_ROLLBACK=true` 기본 정책으로 Blue rollback을 수행한다.
`make deploy-switch-green` 단독 실행도 Green `/health`와 `/ready`를 확인한 뒤 전환한다.
deployment smoke는 기본 `SMOKE_ACCOUNT_NO=ACC-001`을 사용하며, 운영 환경에서는 smoke 전용 계좌를 별도로 지정한다.

DB rollback은 자동화하지 않는다.
Phase 12 rollback은 API traffic rollback이며, schema 변경은 backward-compatible migration 원칙으로 관리한다.
k6 peak/duplicate storm 같은 heavy test는 PR 필수 Gate나 기본 배포 단계가 아니라 수동/릴리즈 전 성능 Gate로 분리한다.

상세 문서:

- [Phase 12 Blue-Green Rollback](./docs/phase-12-blue-green-rollback.md)
- [Deployment Strategy](./docs/09-deployment-strategy.md)

---

## 📈 모니터링 대시보드

### Grafana 접속
```
http://localhost:3000
Username: admin
Password: admin
```

### Prometheus 접속
```
http://localhost:9090
```

로컬 확인 기준:

1. `docker compose up -d`
2. `http://localhost:8000/metrics`에서 `financial_*` metric 확인
3. `http://localhost:9090/targets`에서 `api-server` target UP 확인
4. `http://localhost:3000`에서 `Financial Event Consistency System` dashboard 확인

현재 Prometheus scrape 대상은 Prometheus 자체와 FastAPI `api-server` 중심이다.
Nginx active upstream과 Blue/Green 컨테이너 상태는 `make deploy-status`와 Docker Compose 상태로 확인한다.
`api-green`, Redis exporter, PostgreSQL exporter scrape는 Phase 12 이후 운영 관측 보강 항목이다.

### 주요 대시보드

1. **API Overview** - Request Rate, Response Time, Error Rate
2. **Transaction Consistency** - 중복 이벤트, 잘못된 상태 전이
3. **Database** - Connection 사용률, Transaction Duration
4. **Redis** - Up/Down Status, Cache Hit Ratio
5. **Deployment Monitoring** - Blue-Green 배포 상태

---

## 🛠️ 개발 가이드

### 프로젝트 구조
```
backend/
├── app/
│   ├── main.py                    # FastAPI 애플리케이션 조립
│   ├── api/
│   │   ├── router.py
│   │   └── v1/
│   │       ├── router.py
│   │       └── health.py           # /health, /ready
│   ├── core/
│   │   ├── config.py               # 환경변수 설정
│   │   ├── exceptions.py           # 공통 예외 응답
│   │   └── logging.py              # 구조화 로그
│   ├── db/
│   │   ├── base.py                 # SQLAlchemy Declarative Base
│   │   └── session.py              # DB session, readiness check
│   ├── redis/
│   │   └── client.py               # Redis client, readiness check
│   ├── metrics/
│   │   └── prometheus.py           # /metrics, HTTP metrics
│   ├── schemas/
│   │   └── common.py               # 공통 응답 스키마
│   ├── services/
│   ├── repositories/
│   └── domain/
├── tests/
│   ├── unit/                      # 단위 테스트
│   ├── integration/               # 통합 테스트
│   └── consistency/               # 정합성 테스트
├── Dockerfile
└── requirements.txt
```

### 새로운 기능 추가 체크리스트

- [ ] 상태 머신 테스트 작성
- [ ] 비즈니스 로직 구현
- [ ] API 엔드포인트 작성
- [ ] Integration 테스트 작성
- [ ] 정합성 테스트 추가
- [ ] Consistency Test 통과
- [ ] 문서 업데이트
- [ ] PR 생성

---

## ⚠️ 장애 대응

### Redis 장애
```bash
# 상태 확인
make local-status

# 재시작
docker compose restart redis

# 검증: 정합성은 유지되는가?
curl http://localhost:8000/metrics | grep financial_duplicate_external_event_total
```

### PostgreSQL 연결 문제
```bash
# Connection 확인
psql -U postgres -d financial_events -c "SELECT count(*) FROM pg_stat_activity;"

# 재시작
docker compose restart postgres
```

### API 서버 장애
```bash
# Blue -> Green 전환
make deploy-blue-green

# Rollback
ROLLBACK_REASON="api server failure" make deploy-rollback

# 정합성 검증
make deploy-verify
```

---

## 📖 문서

- [기획 체크리스트](./docs/00-planning-checklist.md)
- [문제 정의](./docs/01-problem-definition.md)
- [도메인 범위](./docs/02-domain-scope.md)
- [정합성 규칙](./docs/03-consistency-rules.md)
- [개발 로드맵과 블로그 산출물 매핑](./docs/04-development-roadmap.md)
- [Architecture Decision Record](./docs/05-architecture-decision-record.md)
- [보안 설계](./docs/06-security-design.md)
- [관측성 설계](./docs/07-observability-design.md)
- [장애 시나리오](./docs/08-failure-scenarios.md)
- [배포 전략](./docs/09-deployment-strategy.md)
- [CANCEL 이벤트 정책](./docs/10-cancel-event-policy.md)
- [API 응답/재시도 정책](./docs/11-api-response-policy.md)
- [데이터 모델 명세](./docs/12-data-model-spec.md)
- [상태 전이표](./docs/13-state-transition-table.md)
- [테스트 케이스 매트릭스](./docs/14-test-case-matrix.md)
- [API Contract](./docs/15-api-contract.md)
- [성능 측정 설계](./docs/16-performance-measurement-design.md)
- [실험 기록 템플릿](./docs/17-experiment-log-template.md)
- [성능 트러블슈팅 가이드](./docs/18-performance-troubleshooting-guide.md)
- [Phase 10 Failure Recovery](./docs/phase-10-failure-recovery.md)
- [Phase 11 CI/CD Gate](./docs/phase-11-ci-cd-gate.md)
- [Phase 12 Blue-Green Rollback](./docs/phase-12-blue-green-rollback.md)

---

## 🎓 배운 점

이 프로젝트를 통해 다음을 배웠습니다:

1. **도메인 주도 설계의 중요성** - 문제를 먼저 깊이 있게 이해
2. **계층별 방어선** - Redis, PostgreSQL, 애플리케이션 로직의 역할 분담
3. **테스트 자동화의 가치** - 정합성 테스트를 배포 Gate로 설정
4. **모니터링의 필수성** - 운영 환경의 건강도를 실시간으로 관측
5. **배포 전략** - Blue-Green으로 무중단, 문제 시 빠른 Rollback
