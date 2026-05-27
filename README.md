# Financial Event Consistency System

> 외부 금융 거래 이벤트의 중복 처리, 순서 꼬임, 재시도 문제를 **Idempotency Key, PostgreSQL Transaction, Redis, 상태 머신, 모니터링**으로 검증하는 백엔드/DevOps 프로젝트

[![CI](https://github.com/dlsrnjs125/Financial-Event-Consistency-System/actions/workflows/ci.yml/badge.svg)](https://github.com/dlsrnjs125/Financial-Event-Consistency-System/actions)

---

## 🎯 프로젝트 목표

금융 시스템에서 가장 중요한 것은 **빠른 응답이 아니라, 중복·재시도·장애 상황에서도 거래 결과가 한 번만 정확하게 반영되는 것**입니다.

이 프로젝트는 다음 5가지를 보장합니다:

1. ✅ **동일 이벤트는 여러 번 들어와도 한 번만 처리**
2. ✅ **동일 Idempotency Key 요청은 항상 같은 결과를 반환**
3. ✅ **잘못된 상태 전이는 차단**
4. ✅ **Redis 장애가 발생해도 최종 정합성은 PostgreSQL에서 보장**
5. ✅ **배포 전 정합성 테스트를 통과하지 못하면 배포 차단**

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
| **Nginx** | Reverse Proxy, Rate Limit, Blue-Green 트래픽 전환 | 외부 요청 관문 |
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
make final-check   # PR 전 format, lint, compile, test 전체 실행
make local-bg      # Docker Compose 스택 백그라운드 실행
make local-stop    # Docker Compose 스택 중지
```

### 주요 엔드포인트

```
GET /health        서버 상태
GET /ready         PostgreSQL, Redis readiness 확인
GET /metrics       Prometheus 메트릭
POST /api/v1/transaction-events
GET /api/v1/transaction-events/{event_id}
GET /api/v1/accounts/{account_no}/balance
```

Phase 5 기준으로 거래 이벤트 수신, 계좌 잔액 조회, Idempotency 응답 재사용, Ledger 기반 balance 반영이 구현되어 있다.
Redis Lock/Cache, HMAC 인증, k6 부하 테스트, 도메인 메트릭 본격화는 후속 Phase에서 구현한다.
금액은 Phase 5 기준 KRW 정수 원 단위로 처리한다.

---

## 📚 기술 블로그 시리즈

이 프로젝트의 설계 과정과 구현 방식을 12편의 기술 블로그로 설명합니다.

1. [왜 금융 이벤트 처리에서 중복 처리가 중요한가?](./blog/01-why-duplicate-event-matters.md)
2. [도메인 모델링과 상태 머신 설계](./blog/02-domain-modeling-state-machine.md)
3. [Idempotency Key로 중복 요청을 방어하는 방법](./blog/03-idempotency-key.md)
4. [PostgreSQL Transaction과 Unique Constraint로 정합성 보장하기](./blog/04-postgresql-transaction.md)
5. [Redis Lock/Cache를 어디까지 믿어야 할까?](./blog/05-redis-lock-cache.md)
6. [잘못된 상태 전이를 막는 테스트 전략](./blog/06-state-transition-test.md)
7. [k6로 중복 이벤트 폭주 상황 재현하기](./blog/07-k6-load-test.md)
8. [Prometheus/Grafana로 거래 이벤트 처리 상태 관측하기](./blog/08-prometheus-grafana.md)
9. [Docker Compose 기반 장애 재현 환경 만들기](./blog/09-docker-compose-failure-test.md)
10. [CI/CD에서 정합성 테스트를 배포 Gate로 사용하는 방법](./blog/10-ci-cd-consistency-gate.md)
11. [Blue-Green 배포와 Rollback 시뮬레이션](./blog/11-blue-green-rollback.md)
12. [프로젝트 회고: 금융권 백엔드에서 정합성과 운영 안정성을 어떻게 설계했는가?](./blog/12-retrospective.md)

---

## 📊 검증 기준

### 정합성 규칙

| 규칙 | 검증 방법 | 목표 |
|-----|---------|------|
| 동일 이벤트는 한 번만 처리 | 100개 동시 요청 → 1개만 반영 | ✅ 0% 중복 |
| Idempotency Key는 같은 응답 반영 | 재전송 → 첫 결과 반환 | ✅ 100% 일치 |
| 다른 Body는 409 Conflict | 다른 금액 + 같은 Key | ✅ 즉시 거부 |
| 잘못된 상태 전이 차단 | COMPLETED → PROCESSING 시도 | ✅ 0% 성공 |
| Redis 없어도 정합성 유지 | Redis Down 후 중복 요청 | ✅ 0% 중복 |

### 성능 지표

| 지표 | 메트릭 이름 | 목표 | 측정 |
|------|-------------|------|------|
| p50 응답시간 | `http_request_duration_seconds` p50 | 50ms 이하 | k6, Prometheus |
| p95 응답시간 | `http_request_duration_seconds` p95 | 300ms 이하 | k6, Prometheus |
| p99 응답시간 | `http_request_duration_seconds` p99 | 1000ms 이하 | k6, Prometheus |
| 에러율 | `http_req_failed`, `http_5xx_total` | 1% 이하 | k6, Prometheus |
| 캐시 히트율 | `redis_keyspace_hits_total` / misses | 80% 이상 | Prometheus |

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
```

모든 개발 작업은 PR 생성 전 `make final-check`로 포맷팅, 린트, Python 컴파일, 테스트를 확인한다.

### 부하 테스트 (k6)
```bash
k6 run tests/k6/smoke-test.js
k6 run tests/k6/peak-load.js
k6 run tests/k6/duplicate-storm.js
```

### 장애 재현 테스트
```bash
# Redis 다운 시뮬레이션
docker-compose pause redis
k6 run tests/k6/consistency-test.js
docker-compose unpause redis

# DB Connection Pool 고갈
export DB_POOL_SIZE=5
docker-compose restart api-blue
k6 run tests/k6/peak-load.js
```

---

## 🔄 CI/CD 파이프라인

모든 PR에서 다음을 자동으로 검사합니다:

```
[PR 생성]
    ↓
[Lint] → [Unit Test] → [Integration Test] → [Consistency Test]
    ↓
[Migration Test] → [Docker Build] → [Secret Scan]
    ↓
[모든 테스트 통과] → ✅ 배포 승인
[하나라도 실패] → ❌ 배포 거부
```

---

## 📈 모니터링 대시보드

### Grafana 접속
```
http://localhost:3000
Username: admin
Password: admin
```

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
docker-compose restart redis

# 검증: 정합성은 유지되는가?
curl http://localhost:8000/metrics | grep financial_events_duplicate_total
```

### PostgreSQL 연결 문제
```bash
# Connection 확인
psql -U postgres -d financial_events -c "SELECT count(*) FROM pg_stat_activity;"

# 재시작
docker-compose restart postgres
```

### API 서버 장애
```bash
# Blue → Green 전환
docker-compose exec nginx bash -c "sed -i 's/api-blue:8000/api-green:8000/g' /etc/nginx/nginx.conf && nginx -s reload"

# 또는 자동 Rollback
./scripts/rollback.sh
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

---

## 🎓 배운 점

이 프로젝트를 통해 다음을 배웠습니다:

1. **도메인 주도 설계의 중요성** - 문제를 먼저 깊이 있게 이해
2. **계층별 방어선** - Redis, PostgreSQL, 애플리케이션 로직의 역할 분담
3. **테스트 자동화의 가치** - 정합성 테스트를 배포 Gate로 설정
4. **모니터링의 필수성** - 운영 환경의 건강도를 실시간으로 관측
5. **배포 전략** - Blue-Green으로 무중단, 문제 시 빠른 Rollback
