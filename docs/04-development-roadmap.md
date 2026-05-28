# 개발 로드맵과 산출물 추적

## 현재 진행 상태

- 현재 위치: **Phase 9 k6 부하 테스트 스크립트 및 기록 템플릿 구현 중**
- GitHub 초기 Push: **완료**
- 다음 단계: **Phase 9 로컬 실행 결과 기록**

Phase 8 완료 범위에는 Prometheus custom metrics, HTTP/transaction/idempotency/Redis/HMAC/state transition metric helper, trace_id/request_id context middleware, 구조화 로그 필드 보강, Grafana dashboard 초안, alert rule 초안, 로컬 Prometheus/Grafana provisioning 구성이 포함된다.
Phase 9 범위에서는 k6 smoke/normal/peak/duplicate/redis-down 시나리오와 결과 기록 문서를 준비한다.
로컬 sanity run으로 smoke와 짧은 duplicate storm 실행은 확인했으며, 정식 p95/p99/RPS/error rate와 Redis 적용 전후 비교 값은 같은 환경을 고정한 반복 실험 후 기록한다.

## 개발 Phase

| 상태 | Phase | 목표 | 주요 산출물 | 완료 기준 |
|------|-------|------|-------------|-----------|
| 완료 | 0. 설계 기준 확정 | 개발 전 기준선 고정 | 설계 문서, 구현 기준, 성능 측정 기준 | 설계 문서와 README 링크 최신화 |
| 완료 | 1. 백엔드 프로젝트 골격 구현 | FastAPI 앱 구조 구성 | 앱 구조, 설정, DB/Redis 연결, Health/Ready | Docker Compose 환경에서 API 실행 |
| 완료 | 2. 데이터 모델과 Migration 구현 | 정합성 기준 DB 모델 구현 | ORM 모델, Alembic Migration, Unique/Index | Migration 성공, 제약조건 테스트 통과 |
| 완료 | 3. 상태 머신 구현 | 허용/금지 상태 전이 구현 | 상태 enum, 전이표, 이력 저장 | 상태 머신 Unit Test 통과 |
| 완료 | 4. Idempotency 처리 구현 | 재시도/충돌 요청 구분 | request_hash, IdempotencyRecord, 응답 재사용 | 같은 Key/Body 재요청 기존 응답 반환 |
| 완료 | 5. Transaction과 Ledger 처리 구현 | 거래 반영 원자성 보장 | TransactionEventService, LedgerService, Row Lock | 동일 이벤트 재요청 시 Ledger 1건 |
| 완료 | 6. Redis Lock/Cache 적용 | 중복 요청 DB 부하 완화 | Redis Lock, Idempotency Cache, fallback | Redis Down 상태에서도 정합성 유지 |
| 완료 | 7. 보안 처리 구현 | 외부 시스템 인증/변조 검증 | HMAC, Timestamp, Secret 관리, 로그 마스킹 | 잘못된 Signature/Timestamp 차단 |
| 완료 | 8. Metrics, Logging, Observability 구현 | 도메인 관측성 확보 | Prometheus metrics, trace_id, Grafana | 주요 도메인 메트릭 노출 |
| 진행 | 9. k6 부하 테스트와 성능 비교 | 설계 선택 수치 검증 | k6 시나리오, 실험 기록, 비교표 | 스크립트와 sanity run 완료, 정식 수치 기록 필요 |
| 대기 | 10. Docker Compose 장애 재현 환경 구성 | 장애 상황 반복 재현 | Redis/DB/API/Nginx 장애 시나리오 | 장애별 정합성 유지 검증 |
| 대기 | 11. CI/CD와 배포 Gate 구성 | 정합성 회귀 자동 차단 | GitHub Actions, Migration Test, Secret Scan | 실패 시 main merge/배포 차단 |
| 대기 | 12. Blue-Green 배포와 Rollback 시뮬레이션 | 검증 후 전환/복구 | Blue/Green, Nginx 전환, rollback script | Green 검증 후 전환, 문제 시 Blue 복귀 |
| 대기 | 13. 블로그 및 회고 정리 | 설계/구현/실험 기록 완성 | README, 블로그 12편, 실험 결과 | 산출물 링크와 수치 기반 회고 정리 |

## 개발 로드맵 관리 기준

각 Phase는 단순 구현 완료가 아니라 다음 4가지를 모두 만족해야 완료로 판단한다.

1. 기능 구현
2. 테스트 통과
3. 메트릭 또는 로그 확인
4. 문서/블로그 반영

또한 각 개발 작업은 PR 생성 전 `make final-check`를 실행해 포맷팅, 린트, Python 컴파일, 테스트를 마지막으로 확인한다.

따라서 각 Phase는 다음 형식으로 관리한다.

- 목표
- 주요 작업
- 검증 기준
- 측정 지표
- 완료 체크리스트
- 연결 문서
- 연결 블로그

## Phase별 상세 관리 기준

### Phase 0. 설계 기준 확정

**목표**

개발을 시작하기 전에 문제 정의, 정합성 기준, 보안, 관측성, 장애, 배포, 성능 측정 기준을 확정한다.

**주요 작업**

- 문제 정의 문서 작성
- 도메인 범위 확정
- 정합성 규칙 정의
- ADR 작성
- 보안 설계 작성
- 관측성 설계 작성
- 장애 시나리오 정의
- 배포/롤백 전략 정의
- CANCEL 정책 정의
- API 응답/재시도 정책 정의
- 성능 측정 설계 작성
- 실험 기록 템플릿 작성
- 성능 트러블슈팅 가이드 작성

**검증 기준**

- 각 주요 설계 결정에 선택 배경과 trade-off가 기록되어 있다.
- Redis를 최종 정합성 기준으로 사용하지 않는 이유가 명확하다.
- CANCEL 이벤트가 삭제가 아니라 보정 거래로 정의되어 있다.
- `account.balance`와 `ledger_entries`의 신뢰 기준이 정리되어 있다.
- 성능 측정 지표와 실험 계획이 정의되어 있다.

**측정 지표**

이 단계에서는 실제 성능 수치를 측정하지 않고, 측정할 지표를 확정한다.

- p50 latency
- p95 latency
- p99 latency
- error rate
- duplicate processing rate
- invalid state transition count
- reconciliation failure count
- DB connection usage
- cache hit ratio

**완료 체크리스트**

- [x] [01-problem-definition.md](01-problem-definition.md) 작성
- [x] [02-domain-scope.md](02-domain-scope.md) 작성
- [x] [03-consistency-rules.md](03-consistency-rules.md) 작성
- [x] [05-architecture-decision-record.md](05-architecture-decision-record.md) 작성
- [x] [06-security-design.md](06-security-design.md) 작성
- [x] [07-observability-design.md](07-observability-design.md) 작성
- [x] [08-failure-scenarios.md](08-failure-scenarios.md) 작성
- [x] [09-deployment-strategy.md](09-deployment-strategy.md) 작성
- [x] [10-cancel-event-policy.md](10-cancel-event-policy.md) 작성
- [x] [11-api-response-policy.md](11-api-response-policy.md) 작성
- [x] [16-performance-measurement-design.md](16-performance-measurement-design.md) 작성
- [x] [17-experiment-log-template.md](17-experiment-log-template.md) 작성
- [x] [18-performance-troubleshooting-guide.md](18-performance-troubleshooting-guide.md) 작성
- [x] README 문서 링크 최신화
- [x] README 메트릭 이름 통일

**연결 블로그**

- 1편. 왜 금융 이벤트 처리 시스템에서 중복 처리가 중요한가?
- 2편. 금융 거래 이벤트 도메인 모델링과 상태 머신 설계
- 5편. Redis Lock/Cache를 어디까지 믿어야 할까?
- 8편. Prometheus/Grafana로 거래 이벤트 처리 상태 관측하기
- 12편. 프로젝트 회고

### Phase 1. 백엔드 프로젝트 골격 구현

**목표**

FastAPI 기반 백엔드 애플리케이션의 기본 구조를 만든다.

**주요 작업**

- FastAPI 앱 초기화
- 환경변수 설정 구조 작성
- DB 연결 설정
- Redis 연결 설정
- Router / Service / Repository / Domain 구조 생성
- 공통 예외 처리 구조 작성
- 공통 응답 포맷 정의
- `/health` endpoint 구현
- `/ready` endpoint 구현

**검증 기준**

- Docker Compose 환경에서 API 서버가 정상 실행된다.
- `/health`가 200 OK를 반환한다.
- `/ready`가 PostgreSQL, Redis 연결 상태를 확인한다.
- 환경변수 없이 민감값이 코드에 하드코딩되어 있지 않다.

**측정 지표**

- health check latency
- ready check latency
- API startup time
- dependency connection success/failure

**완료 체크리스트**

- [x] FastAPI 앱 실행 가능
- [x] Router / Service / Repository / Domain 폴더 구조 생성
- [x] settings/config 모듈 작성
- [x] PostgreSQL 연결 확인
- [x] Redis 연결 확인
- [x] `/health` 구현
- [x] `/ready` 구현
- [x] 공통 예외 응답 구조 작성
- [x] 기본 로그 포맷 적용
- [x] Dockerfile 작성

**연결 문서**

- [05-architecture-decision-record.md](05-architecture-decision-record.md)
- [06-security-design.md](06-security-design.md)
- [07-observability-design.md](07-observability-design.md)

**연결 블로그**

- 9편. Docker Compose 기반 장애 재현 환경 만들기

### Phase 2. 데이터 모델과 Migration 구현

**목표**

거래 이벤트 정합성의 기준이 되는 데이터 모델을 구현한다.

**주요 작업**

- Account 모델 구현
- TransactionEvent 모델 구현
- LedgerEntry 모델 구현
- IdempotencyRecord 모델 구현
- EventStateHistory 모델 구현
- Alembic 초기 Migration 작성
- Unique Constraint 작성
- Index 작성

**검증 기준**

- `external_event_id`는 중복 저장되지 않는다.
- `idempotency_key`는 중복 저장되지 않는다.
- 하나의 `transaction_event_id`는 `ledger_entries`에 한 번만 연결된다.
- Migration upgrade가 성공한다.
- Migration downgrade 또는 재적용 전략이 문서화되어 있다.

**측정 지표**

- migration execution time
- index creation time
- insert latency
- duplicate insert failure count

**완료 체크리스트**

- [x] accounts 테이블 구현
- [x] transaction_events 테이블 구현
- [x] ledger_entries 테이블 구현
- [x] idempotency_records 테이블 구현
- [x] event_state_histories 테이블 구현
- [x] external_event_id UNIQUE 적용
- [x] idempotency_key UNIQUE 적용
- [x] ledger_entries.transaction_event_id UNIQUE 적용
- [x] 주요 조회 컬럼 Index 적용
- [x] Alembic upgrade 성공
- [x] Migration 테스트 추가

**연결 문서**

- [03-consistency-rules.md](03-consistency-rules.md)
- [09-deployment-strategy.md](09-deployment-strategy.md)
- [10-cancel-event-policy.md](10-cancel-event-policy.md)
- [12-data-model-spec.md](12-data-model-spec.md)
- [16-performance-measurement-design.md](16-performance-measurement-design.md)

**연결 블로그**

- 2편. 금융 거래 이벤트 도메인 모델링과 상태 머신 설계
- 4편. PostgreSQL Transaction과 Unique Constraint로 정합성 보장하기

### Phase 3. 상태 머신 구현

**목표**

거래 이벤트의 허용 상태 전이와 금지 상태 전이를 코드로 구현한다.

**주요 작업**

- 상태 enum 정의
- 허용 상태 전이표 구현
- InvalidStateTransition 예외 구현
- EventStateHistory 저장 로직 구현
- CANCEL 가능 상태 검증
- SETTLED 이후 CANCEL 금지 정책 구현

**검증 기준**

- 허용된 상태 전이는 성공한다.
- 금지된 상태 전이는 예외를 발생시킨다.
- 상태 변경 이력이 저장된다.
- `COMPLETED -> PROCESSING`은 실패한다.
- `FAILED -> COMPLETED`는 실패한다.
- `SETTLED -> CANCELLED`는 실패한다.

**측정 지표**

- `financial_invalid_state_transition_total`
- state transition validation latency
- state transition test duration

**완료 체크리스트**

- [x] 상태 enum 작성
- [x] 허용 상태 전이표 작성
- [x] 상태 전이 검증 함수 작성
- [x] InvalidStateTransition 예외 작성
- [x] EventStateHistory 저장
- [x] 상태 머신 단위 테스트 작성
- [x] 금지 상태 전이 테스트 작성
- [x] CANCEL 관련 상태 테스트 작성

**연결 문서**

- [03-consistency-rules.md](03-consistency-rules.md)
- [10-cancel-event-policy.md](10-cancel-event-policy.md)
- [13-state-transition-table.md](13-state-transition-table.md)
- [16-performance-measurement-design.md](16-performance-measurement-design.md)

**연결 블로그**

- 2편. 금융 거래 이벤트 도메인 모델링과 상태 머신 설계
- 6편. 잘못된 상태 전이를 막는 테스트 전략

### Phase 4. Idempotency 처리 구현

**목표**

동일 요청 재전송과 충돌 요청을 구분하고, 중복 거래 반영을 방지한다.

**주요 작업**

- Idempotency-Key 필수 검증
- request_hash 생성
- IdempotencyRecord 저장
- 같은 Key + 같은 Body 처리
- 같은 Key + 다른 Body 409 처리
- PROCESSING 상태 재요청 202 처리
- 완료 요청 재전송 시 기존 응답 반환
- 완료/실패 저장 시 원 요청 hash와 응답 저장 대상 key 일치 여부 검증
- 완료/실패 저장 시 `PROCESSING` 상태에서만 terminal 상태로 변경
- 실패 응답 저장 시 운영 추적용 error_message 저장

**검증 기준**

- 같은 Idempotency-Key와 같은 Body는 기존 응답을 반환한다.
- 같은 Idempotency-Key와 다른 Body는 409 Conflict를 반환한다.
- 처리 중 동일 요청은 202 Accepted를 반환한다.
- 완료된 동일 요청은 거래를 다시 반영하지 않는다.
- `expires_at`은 Phase 4에서 보관 정책 기준으로만 사용하고, 요청 시점 자동 무효화는 수행하지 않는다.
- `COMPLETED -> FAILED`, `FAILED -> COMPLETED` 전환은 차단한다.
- 만료 삭제는 `COMPLETED`, `FAILED` record만 대상으로 한다.

**측정 지표**

- `financial_idempotency_hit_total`
- `financial_idempotency_conflict_total`
- `financial_duplicate_external_event_total`
- idempotency lookup latency

**완료 체크리스트**

- [x] Idempotency-Key Header 검증
- [x] request_hash 생성 로직 작성
- [x] IdempotencyRecord Repository 작성
- [x] 동일 요청 재전송 처리
- [x] 충돌 요청 409 처리
- [x] 처리 중 요청 202 처리
- [x] 완료 응답 재사용 처리
- [x] 완료/실패 저장 시 request_hash 검증
- [x] 완료/실패 저장 시 terminal 상태 전환 guard 적용
- [x] 실패 사유 error_message 저장
- [x] Idempotency 테스트 작성

**연결 문서**

- [06-security-design.md](06-security-design.md)
- [11-api-response-policy.md](11-api-response-policy.md)
- [15-api-contract.md](15-api-contract.md)
- [16-performance-measurement-design.md](16-performance-measurement-design.md)

**테스트 한계**

현재 Repository integration test는 빠른 회귀 검증을 위해 SQLite in-memory 기반으로 수행한다.
PostgreSQL 고유 동작(JSONB, timestamptz, concurrent unique conflict)은 Phase 5 이후 Docker Compose 기반 integration test에서 검증한다.

**연결 블로그**

- 3편. Idempotency Key로 중복 요청을 방어하는 방법

### Phase 5. Transaction과 Ledger 처리 구현

**목표**

거래 이벤트 저장, 원장 생성, 잔액 변경을 하나의 Transaction으로 묶어 정합성을 보장한다.

**주요 작업**

- TransactionEventService 구현
- LedgerService 구현
- Account balance 변경 로직 구현
- Row Lock 적용
- Unique Constraint 충돌 처리
- DEPOSIT 처리
- WITHDRAW 처리
- CANCEL 보정 거래 처리
- `POST /api/v1/transaction-events` 구현
- `GET /api/v1/transaction-events/{event_id}` 구현
- `GET /api/v1/accounts/{account_no}/balance` 구현

**검증 기준**

- 동일 `external_event_id`는 한 번만 저장된다.
- 동일 이벤트로 `ledger_entries`가 두 번 생성되지 않는다.
- 동일 `external_event_id`가 다른 거래 내용으로 재요청되면 duplicate가 아니라 도메인 실패로 처리한다.
- DEPOSIT은 balance를 증가시킨다.
- WITHDRAW는 balance를 감소시킨다.
- CANCEL은 원거래 반대 방향 LedgerEntry를 생성한다.
- Transaction 실패 시 LedgerEntry와 Account balance는 반영하지 않고, 생성된 TransactionEvent는 `FAILED` 상태로 마감한다.
- 동일 Idempotency-Key와 같은 Body는 저장된 응답을 반환한다.
- 동일 Idempotency-Key와 다른 Body는 409로 매핑 가능하다.

**측정 지표**

- `financial_db_transaction_duration_seconds`
- `financial_ledger_entries_created_total`
- `financial_events_processed_total`
- `financial_events_failed_total`
- duplicate processing rate

**완료 체크리스트**

- [x] TransactionEventService 작성
- [x] LedgerService 작성
- [x] Account row lock 적용
- [x] DEPOSIT 처리 구현
- [x] WITHDRAW 처리 구현
- [x] CANCEL 처리 구현
- [x] Unique Constraint 충돌 처리 기반 유지
- [x] Transaction 처리 integration test 작성
- [x] 동일 이벤트 순차 재요청 Ledger 1건 테스트 작성
- [x] 동일 external_event_id 다른 Body 방어 테스트 작성
- [x] 실패 이벤트 FAILED 상태 마감 테스트 작성
- [x] 거래 이벤트 API 테스트 작성

**테스트 한계**

현재 Phase 5 integration test는 빠른 회귀 검증을 위해 SQLite in-memory 기반으로 수행한다.
SQLite에서는 `SELECT FOR UPDATE`와 concurrent unique conflict 검증이 제한되므로, 동일 이벤트 100회 동시 요청과 PostgreSQL row lock 검증은 Phase 6 이후 Docker Compose 기반 integration test에서 보강한다.

**구현 정책**

거래 처리 중 발생한 도메인 실패는 Idempotency failed response 재사용을 위해 TransactionEventService에서 표준 실패 body로 변환한다.
요청 검증, Header 누락, 조회성 API 오류는 공통 exception handler가 HTTP 응답으로 변환한다.
Phase 5는 KRW 정수 원 단위를 기준으로 `amount`와 `balance`를 `bigint`/`int`로 관리한다.
소수 통화 또는 외화 소수점 처리는 후속 데이터 모델 확장에서 검토한다.

**연결 문서**

- [03-consistency-rules.md](03-consistency-rules.md)
- [10-cancel-event-policy.md](10-cancel-event-policy.md)
- [16-performance-measurement-design.md](16-performance-measurement-design.md)
- [18-performance-troubleshooting-guide.md](18-performance-troubleshooting-guide.md)

**연결 블로그**

- 4편. PostgreSQL Transaction과 Unique Constraint로 정합성 보장하기

### Phase 6. Redis Lock/Cache 적용

**목표**

Redis를 사용해 중복 요청의 DB 진입을 줄이고, 완료된 Idempotency 응답을 빠르게 반환한다.

**주요 작업**

- RedisLock 구현
- Idempotency Cache 구현
- `lock:idempotency:{sha256(idempotency_key)}` 설계
- `cache:idempotency:{sha256(idempotency_key)}` 설계
- CachedIdempotencyService 구현
- TransactionEventService optional Redis Lock 통합
- Redis 장애 fallback 구현
- TTL 정책 적용

**검증 기준**

- Redis Cache Hit 시 DB 조회 없이 기존 응답을 반환한다.
- Redis Lock 획득 실패 시 DB transaction 진입 전 `202 Accepted`를 반환한다.
- Redis가 다운되어도 PostgreSQL 기준 정합성은 유지된다.
- Redis 장애 시 API가 즉시 전체 장애로 전파되지 않는다.
- Phase 6에서는 Redis unavailable fallback의 순차 회귀 테스트를 수행한다.
- 동시 duplicate storm에서 Redis 적용 전후 p95/p99, DB transaction count, duplicate rate는 Phase 9 k6/PostgreSQL 환경에서 검증한다.

**측정 지표**

- cache hit ratio
- `financial_idempotency_cache_hit_total`
- `financial_idempotency_cache_miss_total`
- `financial_redis_lock_rejected_total`
- `financial_redis_unavailable_total`
- `financial_idempotency_cache_hit_total`
- `financial_idempotency_cache_miss_total`
- Redis 적용 전후 p95/p99 latency
- DB transaction count

**완료 체크리스트**

- [x] Redis client timeout 설정
- [x] RedisLock 작성
- [x] owner token 기반 release 구현
- [x] 원문 Idempotency-Key를 숨기는 Redis key 생성 함수 구현
- [x] Idempotency Cache 저장/조회 구현
- [x] CachedIdempotencyService 작성
- [x] TransactionEventService optional Redis Lock 통합
- [x] TTL 정책 적용
- [x] Redis Down fallback 구현
- [x] Redis 관련 Unit Test 작성
- [x] Redis Down 상태 동일 이벤트 순차 재요청 중복 반영 0건 테스트 작성
- [x] Redis Cache/Lock 성능 비교 측정 항목 문서화

**연결 문서**

- [05-architecture-decision-record.md](05-architecture-decision-record.md)
- [07-observability-design.md](07-observability-design.md)
- [08-failure-scenarios.md](08-failure-scenarios.md)
- [16-performance-measurement-design.md](16-performance-measurement-design.md)
- [17-experiment-log-template.md](17-experiment-log-template.md)

**연결 블로그**

- 5편. Redis Lock/Cache를 어디까지 믿어야 할까?
- 7편. k6로 중복 이벤트 폭주 상황 재현하기

### Phase 7. 보안 처리 구현

**목표**

외부 시스템 인증과 요청 변조 검증을 적용한다.

**주요 작업**

- `X-Client-Id` 검증
- `X-Timestamp` 검증
- `X-Signature` 검증
- HMAC Signature 생성/검증
- Timestamp 허용 범위 검증
- env 기반 Client Secret Provider 구현
- Security dependency 적용
- 로그 마스킹 helper 구현

**검증 기준**

- 잘못된 client_id는 401 또는 403을 반환한다.
- 잘못된 signature는 401을 반환한다.
- timestamp 허용 범위를 벗어나면 401을 반환한다.
- Secret은 로그에 남지 않는다.
- 계좌번호는 마스킹된다.
- 인증 실패 요청은 IdempotencyRecord, TransactionEvent, LedgerEntry를 생성하지 않는다.

**측정 지표**

- `financial_external_auth_failed_total` (Phase 8 측정 예정)
- `financial_hmac_signature_invalid_total` (Phase 8 측정 예정)
- auth validation latency

**완료 체크리스트**

- [x] `X-Client-Id` 검증
- [x] `X-Timestamp` 검증
- [x] `X-Signature` 검증
- [x] HMAC 검증 유틸 작성
- [x] Signature base string 문서화
- [x] Timestamp ±5분 정책 적용
- [x] env 기반 Client Secret Provider 작성
- [x] POST 거래 이벤트 API Security dependency 적용
- [x] 인증 실패 테스트 작성
- [x] 인증 실패 시 DB row 미생성 테스트 작성
- [x] 로그 마스킹 테스트 작성
- [x] Secret 하드코딩 방지 기준 문서화

**연결 문서**

- [06-security-design.md](06-security-design.md)
- [11-api-response-policy.md](11-api-response-policy.md)

**연결 블로그**

- 3편. Idempotency Key로 중복 요청을 방어하는 방법

### Phase 8. Metrics, Logging, Observability 구현

**목표**

Prometheus 메트릭과 구조화 로그를 구현해 거래 이벤트 처리 흐름을 관측 가능하게 만든다.

**주요 작업**

- `/metrics` endpoint 구현
- Prometheus client 적용
- 도메인 메트릭 추가
- trace_id 생성
- request_id 생성
- event_id/external_event_id/idempotency_key 로그 포함
- Grafana Dashboard JSON 작성
- Grafana datasource/dashboard provisioning 작성
- Alert Rule 초안 작성

**검증 기준**

- `/metrics`에서 주요 메트릭이 노출된다.
- 거래 이벤트 처리 시 도메인 메트릭이 증가한다.
- 잘못된 상태 전이 시 `financial_invalid_state_transition_total`이 증가한다.
- trace_id로 하나의 이벤트 처리 흐름을 추적할 수 있다.
- 응답 Header에 `X-Trace-ID`, `X-Request-ID`가 포함된다.
- Grafana/Alert 초안은 존재하되 운영 임계값은 Phase 9 측정 후 조정한다.
- `docker compose up -d` 후 Prometheus target과 Grafana dashboard를 로컬에서 확인할 수 있다.
- Redis/PostgreSQL exporter는 Phase 8 범위에서 제외하고 앱 도메인 메트릭을 우선 확인한다.

**측정 지표**

- `financial_http_requests_total`
- `financial_http_request_duration_seconds`
- `financial_transaction_events_total`
- `financial_transaction_processing_duration_seconds`
- `financial_duplicate_external_event_total`
- `financial_idempotency_decisions_total`
- `financial_idempotency_conflict_total`
- `financial_redis_lock_acquired_total`
- `financial_redis_lock_rejected_total`
- `financial_idempotency_cache_hit_total`
- `financial_idempotency_cache_miss_total`
- `financial_hmac_auth_failures_total`
- `financial_invalid_state_transition_total`
- `financial_reconciliation_failures_total`

**완료 체크리스트**

- [x] `/metrics` 구현 유지
- [x] API latency metric 추가
- [x] transaction 처리 metric 추가
- [x] idempotency decision metric 추가
- [x] Redis lock/cache metric 추가
- [x] HMAC 인증 성공/실패 metric 추가
- [x] 상태 전이 실패 metric 추가
- [x] reconciliation 실패 metric 기반 추가
- [x] 구조화 로그 필드 보강
- [x] trace_id/request_id context middleware 적용
- [x] Grafana Dashboard 초안 작성
- [x] Grafana datasource/dashboard provisioning 작성
- [x] Alert Rule 초안 작성
- [x] Observability unit/integration test 작성

**연결 문서**

- [07-observability-design.md](07-observability-design.md)
- [16-performance-measurement-design.md](16-performance-measurement-design.md)
- [18-performance-troubleshooting-guide.md](18-performance-troubleshooting-guide.md)

**연결 블로그**

- 8편. Prometheus/Grafana로 거래 이벤트 처리 상태 관측하기

### Phase 9. k6 부하 테스트와 성능 비교

**목표**

설계 선택에 따른 성능 차이와 장애 상황에서의 정합성 유지 여부를 수치로 검증한다.

**주요 작업**

- smoke-test.js 작성
- normal-load.js 작성
- peak-load.js 작성
- duplicate-storm.js 작성
- redis-down-test.js 작성
- DB Pool size 비교 실험
- Redis Cache 전후 비교 실험
- Redis Lock 전후 비교 실험
- Transaction 범위 비교 실험

**검증 기준**

- duplicate storm에서도 ledger 중복 생성이 없어야 한다.
- Redis Down 상태에서도 duplicate processing rate는 0%여야 한다.
- DB Pool 고갈 시 일부 503은 허용하지만 정합성은 유지되어야 한다.
- 성능 실험 결과가 docs/17 실험 기록 형식으로 남아야 한다.

**측정 지표**

- p50 latency
- p95 latency
- p99 latency
- error rate
- duplicate processing rate
- cache hit ratio
- DB connection usage
- transaction duration

**완료 체크리스트**

- [x] smoke-test.js 작성
- [x] normal-load.js 작성
- [x] peak-load.js 작성
- [x] duplicate-storm.js 작성
- [x] redis-down-test.js 작성
- [x] k6 HMAC 공통 helper 작성
- [x] Redis Cache/Lock, DB Pool 비교 실행 타겟 작성
- [x] PostgreSQL 정합성 검증 SQL/Makefile 타겟 작성
- [x] Phase 9 결과 기록 문서 작성
- [ ] Redis Cache 전후 결과 기록
- [ ] Redis Lock 전후 결과 기록
- [ ] DB Pool size 비교 결과 기록
- [ ] Transaction 범위 비교 결과 기록
- [x] README Phase 9 실행 방법 반영
- [ ] 실제 측정 결과를 README와 블로그에 반영

**연결 문서**

- [16-performance-measurement-design.md](16-performance-measurement-design.md)
- [17-experiment-log-template.md](17-experiment-log-template.md)
- [18-performance-troubleshooting-guide.md](18-performance-troubleshooting-guide.md)

**연결 블로그**

- 7편. k6로 중복 이벤트 폭주 상황 재현하기
- 5편. Redis Lock/Cache를 어디까지 믿어야 할까?
- 12편. 프로젝트 회고

### Phase 10. Docker Compose 장애 재현 환경 구성

**목표**

Redis, DB, API, Nginx 장애를 로컬에서 반복 재현할 수 있게 한다.

**주요 작업**

- docker-compose.yml 구성
- PostgreSQL service 구성
- Redis service 구성
- Nginx service 구성
- Prometheus service 구성
- Grafana service 구성
- 장애 재현 스크립트 작성

**검증 기준**

- `docker compose up`으로 전체 환경이 실행된다.
- Redis Down 시나리오가 재현된다.
- DB Pool 고갈 시나리오가 재현된다.
- API Restart 시나리오가 재현된다.
- Nginx 전환 실패 시나리오가 재현된다.

**측정 지표**

- `financial_redis_unavailable_total`
- `db_connections_active` (PostgreSQL exporter 도입 후)
- `financial_http_errors_total`
- `financial_events_failed_total`
- `financial_redis_lock_rejected_total`

**완료 체크리스트**

- [ ] docker-compose.yml 작성
- [ ] PostgreSQL 컨테이너 실행
- [ ] Redis 컨테이너 실행
- [ ] Nginx 컨테이너 실행
- [ ] Prometheus 컨테이너 실행
- [ ] Grafana 컨테이너 실행
- [ ] Redis Down 스크립트 작성
- [ ] DB Pool 고갈 실험 작성
- [ ] API Restart 실험 작성

**연결 문서**

- [08-failure-scenarios.md](08-failure-scenarios.md)
- [09-deployment-strategy.md](09-deployment-strategy.md)

**연결 블로그**

- 9편. Docker Compose 기반 장애 재현 환경 만들기

### Phase 11. CI/CD와 배포 Gate 구성

**목표**

정합성을 깨는 코드가 main 브랜치에 들어가거나 배포되지 않도록 자동 검증한다.

**주요 작업**

- GitHub Actions CI 작성
- Lint 단계 작성
- Unit Test 단계 작성
- Integration Test 단계 작성
- Consistency Test 단계 작성
- Migration Test 단계 작성
- Docker Build 단계 작성
- Secret Scan 단계 작성

**검증 기준**

- 상태 머신 테스트 실패 시 CI가 실패한다.
- Idempotency 테스트 실패 시 CI가 실패한다.
- Migration 실패 시 CI가 실패한다.
- Secret이 포함되면 CI가 실패한다.
- Docker build 실패 시 CI가 실패한다.

**측정 지표**

- unit test duration
- integration test duration
- consistency test duration
- migration test duration
- total CI duration
- failed deployment prevented count

**완료 체크리스트**

- [ ] ci.yml 작성
- [ ] Lint 단계 추가
- [ ] Unit Test 단계 추가
- [ ] Integration Test 단계 추가
- [ ] Consistency Test 단계 추가
- [ ] Migration Test 단계 추가
- [ ] Docker Build 단계 추가
- [ ] Secret Scan 단계 추가
- [ ] CI 실패 사례 문서화

**연결 문서**

- [09-deployment-strategy.md](09-deployment-strategy.md)
- [16-performance-measurement-design.md](16-performance-measurement-design.md)

**연결 블로그**

- 10편. CI/CD에서 정합성 테스트를 배포 Gate로 사용하는 방법

### Phase 12. Blue-Green 배포와 Rollback 시뮬레이션

**목표**

Green 버전을 검증한 후 트래픽을 전환하고, 문제 발생 시 Blue로 되돌릴 수 있게 한다.

**주요 작업**

- api-blue 구성
- api-green 구성
- Nginx upstream 설정
- deploy-green.sh 작성
- switch-green.sh 작성
- rollback-blue.sh 작성
- Green 검증 스크립트 작성

**검증 기준**

- Green 전환 전 `/health`, `/ready`가 성공한다.
- Green 전환 전 smoke test가 성공한다.
- Green 전환 전 consistency test가 성공한다.
- Green 전환 후 p95, 5xx, invalid transition을 확인한다.
- rollback 시 Blue로 트래픽이 복구된다.

**측정 지표**

- Blue p95 latency
- Green p95 latency
- Blue 5xx rate
- Green 5xx rate
- `financial_invalid_state_transition_total`
- `financial_reconciliation_failures_total`

**완료 체크리스트**

- [ ] api-blue 구성
- [ ] api-green 구성
- [ ] Nginx upstream Blue 설정
- [ ] Green 배포 스크립트 작성
- [ ] Nginx Green 전환 스크립트 작성
- [ ] Rollback 스크립트 작성
- [ ] Blue/Green 전후 지표 비교 기록
- [ ] rollback 시나리오 문서화

**연결 문서**

- [09-deployment-strategy.md](09-deployment-strategy.md)
- [18-performance-troubleshooting-guide.md](18-performance-troubleshooting-guide.md)

**연결 블로그**

- 11편. Blue-Green 배포와 Rollback 시뮬레이션

### Phase 13. 블로그 및 회고 정리

**목표**

설계, 구현, 실험, 장애 재현, 성능 비교 결과를 기술 블로그와 README에 반영한다.

**주요 작업**

- 블로그 1~12편 작성
- 성능 실험 결과 반영
- 장애 재현 결과 반영
- Grafana 대시보드 캡처 추가
- k6 결과 표 추가
- 트러블슈팅 기록 작성
- README 최종 업데이트

**검증 기준**

- 각 블로그 글이 실제 코드/테스트/실험 결과와 연결되어 있다.
- 성능 비교 수치가 기록되어 있다.
- 장애 재현 결과가 기록되어 있다.
- 설계 변경 이유와 trade-off가 기록되어 있다.

**완료 체크리스트**

- [ ] 1편 작성
- [ ] 2편 작성
- [ ] 3편 작성
- [ ] 4편 작성
- [ ] 5편 작성
- [ ] 6편 작성
- [ ] 7편 작성
- [ ] 8편 작성
- [ ] 9편 작성
- [ ] 10편 작성
- [ ] 11편 작성
- [ ] 12편 작성
- [ ] README 최종 업데이트
- [ ] 트러블슈팅 문서 작성

**연결 문서**

- [16-performance-measurement-design.md](16-performance-measurement-design.md)
- [17-experiment-log-template.md](17-experiment-log-template.md)
- [18-performance-troubleshooting-guide.md](18-performance-troubleshooting-guide.md)

## 완료 체크 기록

| 항목 | 상태 | 비고 |
|------|------|------|
| 기획 문서 작성 | 완료 | 문제 정의, 도메인 범위, 정합성 규칙 정리 |
| ADR 문서 작성 | 완료 | 주요 기술 선택, 대안, trade-off, 보완 전략 정리 |
| 보안/관측성/장애/배포 설계 문서 작성 | 완료 | Security, Observability, Failure Scenario, Deployment Strategy 정리 |
| 도메인 보완 정책 문서 작성 | 완료 | CANCEL 정책, API 응답/재시도 정책 정리 |
| 구현 기준 문서 작성 | 완료 | 데이터 모델 명세, 상태 전이표, 테스트 매트릭스, API Contract 정리 |
| 성능 측정 기준 문서 작성 | 완료 | 성능 측정 설계, 실험 기록 템플릿, 성능 트러블슈팅 가이드 정리 |
| README 초안 작성 | 완료 | 프로젝트 목표, 실행 방법, 검증 기준 정리 |
| Docker Compose 기반 인프라 골격 | 완료 | PostgreSQL, Redis, API, Nginx, Prometheus, Grafana 구성 |
| FastAPI 기본 엔트리포인트 | 완료 | Health, Ready, Metrics, placeholder API 구성 |
| Phase 1 백엔드 프로젝트 골격 구현 | 완료 | FastAPI 앱 구조, 설정, DB/Redis readiness, 예외 응답, 기본 로그 포맷, Dockerfile 구성 |
| Phase 2 데이터 모델과 Migration 구현 | 완료 | ORM 모델 5개, Alembic metadata 연결, 초기 Migration, Unique/Index, 모델 검증 테스트 구성 |
| Phase 3 상태 머신 구현 | 완료 | TransactionStatus enum, 상태 전이표, InvalidStateTransition, EventStateHistory 저장 기반, 상태 머신 테스트 구성 |
| Phase 4 Idempotency 처리 기반 구현 | 완료 | request_hash, Header 검증 dependency, IdempotencyRecord Repository, IdempotencyService, 응답 재사용 판단 테스트 구성 |
| 테스트/부하 테스트 골격 | 완료 | Unit Test, Consistency Test skeleton, k6 시나리오 초안 |
| 배포/롤백 스크립트 골격 | 완료 | Blue-Green 전환과 rollback 스크립트 초안 |
| GitHub 초기 Push | 완료 | `main` 브랜치가 원격 저장소 `origin/main`을 추적 |

## 블로그 산출물 매핑

| 편 | 글 | 연결 산출물 | 보여줄 코드/테스트/실험 |
|----|----|-------------|--------------------------|
| 1 | 왜 금융 이벤트 처리에서 중복 처리가 중요한가? | 문제 정의 문서, 정합성 규칙 | 중복 입금 시나리오, 동일 이벤트 100회 검증 기준 |
| 2 | 도메인 모델링과 상태 머신 설계 | ERD 초안, 상태 머신 초안 | 엔티티 정의, 허용/금지 상태 전이, 상태 머신 Unit Test |
| 3 | Idempotency Key로 중복 요청을 방어하는 방법 | IdempotencyRecord 설계 | request_hash 비교, 같은 Key/다른 Body 409 테스트 |
| 4 | PostgreSQL Transaction과 Unique Constraint로 정합성 보장하기 | DB schema, transaction 처리 흐름 | `external_event_id` UNIQUE, Ledger 1:1 제약, 동시 요청 테스트 |
| 5 | Redis Lock/Cache를 어디까지 믿어야 할까? | Redis lock/cache 설계 | Redis 장애 fallback 코드, Redis Down 중복 방지 테스트 |
| 6 | 잘못된 상태 전이를 막는 테스트 전략 | 상태 머신 테스트, CI gate | `COMPLETED -> PROCESSING` 차단 테스트, 배포 차단 기준 |
| 7 | k6로 중복 이벤트 폭주 상황 재현하기 | k6 smoke/peak/duplicate 시나리오 | p50/p95/p99, 중복 반영 0건 검증 SQL |
| 8 | Prometheus/Grafana로 거래 이벤트 처리 상태 관측하기 | metrics endpoint, alert rule, dashboard | 중복 이벤트 카운터, 에러율, DB/Redis 지표 |
| 9 | Docker Compose 기반 장애 재현 환경 만들기 | `docker-compose.yml`, 장애 재현 스크립트 | Redis 중지, DB Pool 고갈, API 재시작 실험 |
| 10 | CI/CD에서 정합성 테스트를 배포 Gate로 사용하는 방법 | GitHub Actions workflow | lint/unit/consistency/migration/docker gate 결과 |
| 11 | Blue-Green 배포와 Rollback 시뮬레이션 | Nginx 설정, deploy/rollback script | Green 헬스체크, 트래픽 전환, rollback 실행 로그 |
| 12 | 프로젝트 회고 | 전체 산출물 요약 | 설계 판단, 테스트에서 발견한 리스크, 운영 안정성 회고 |

## README 초안 목차

1. 프로젝트 목표
2. 시스템 아키텍처
3. 빠른 시작
4. 주요 엔드포인트
5. 기술 블로그 시리즈
6. 검증 기준
7. 테스트 전략
8. CI/CD 파이프라인
9. 모니터링 대시보드
10. 개발 가이드
11. 장애 대응
12. 문서
13. 배운 점

## 남은 구현 메모

- 현재 백엔드는 Phase 4 Idempotency 처리 기반 구현 완료 상태이므로 거래 이벤트 API의 실제 처리 로직은 Phase 5 이후 구현한다.
- Consistency Test 파일은 테스트 시나리오 골격을 먼저 잡은 상태이며, Transaction/Idempotency 처리 구현 후 skip을 제거한다.
- Phase 5에서는 TransactionEventService, LedgerService, Account row lock, DEPOSIT/WITHDRAW/CANCEL 반영, rollback 검증을 구현한다.
- Phase 5 완료 후 동일 external_event_id 중복 요청 방어와 Ledger 1건 보장 테스트를 실제 앱 코드 기준으로 통과시키고, 이 문서의 Phase 5 상태를 `완료`로 변경한다.
- 설계 결정은 [05-architecture-decision-record.md](05-architecture-decision-record.md)에 ADR 형식으로 기록하고, 새로운 기술 선택이 생길 때 같은 구조로 추가한다.
- 구현 단계에서는 [12-data-model-spec.md](12-data-model-spec.md), [13-state-transition-table.md](13-state-transition-table.md), [14-test-case-matrix.md](14-test-case-matrix.md), [15-api-contract.md](15-api-contract.md)를 기준으로 모델, 상태 머신, 테스트, API 스키마를 작성한다.
- 성능 실험은 [16-performance-measurement-design.md](16-performance-measurement-design.md), [17-experiment-log-template.md](17-experiment-log-template.md), [18-performance-troubleshooting-guide.md](18-performance-troubleshooting-guide.md)를 기준으로 기록한다.

## 프로젝트 완료 기준

이 프로젝트는 단순히 API가 동작하는 시점이 아니라 다음 조건을 만족했을 때 완료로 본다.

### 기능 완료

- [ ] DEPOSIT 이벤트 처리
- [ ] WITHDRAW 이벤트 처리
- [ ] CANCEL 이벤트 처리
- [ ] Idempotency-Key 처리
- [ ] 상태 머신 처리
- [ ] LedgerEntry 기반 잔액 변경

### 정합성 완료

- [ ] 동일 external_event_id 중복 반영 0건
- [ ] 동일 Idempotency-Key 재요청 기존 응답 반환
- [ ] 같은 Key 다른 Body 409 반환
- [ ] 잘못된 상태 전이 차단
- [ ] CANCEL은 보정 LedgerEntry로 처리
- [ ] Reconciliation 검증 가능

### 보안 완료

- [ ] HMAC Signature 검증
- [ ] Timestamp 검증
- [ ] Secret 하드코딩 없음
- [ ] 로그 마스킹 적용
- [ ] 인증 실패 메트릭 수집

### 성능/운영 완료

- [ ] p95 latency 목표 측정
- [ ] p99 latency 목표 측정
- [ ] Redis Cache 전후 비교
- [ ] DB Pool size 비교
- [ ] Transaction 범위 비교
- [ ] Redis Down 장애 재현
- [ ] DB Pool 고갈 재현
- [ ] Prometheus 메트릭 수집
- [ ] Grafana Dashboard 구성

### DevOps 완료

- [ ] Docker Compose 실행 가능
- [ ] GitHub Actions CI 구성
- [ ] Consistency Test CI Gate 적용
- [ ] Migration Test 적용
- [ ] Blue-Green 배포 시뮬레이션
- [ ] Rollback 시나리오 검증

### 문서 완료

- [ ] README 최신화
- [ ] docs 문서 최신화
- [ ] 실험 결과 기록
- [ ] 장애 재현 기록
- [ ] 블로그 12편 작성
