# 금융 이벤트 정합성 시스템 - 도메인 범위

## 개요

이 프로젝트는 실제 금융기관 연동이 아니라, **금융 이벤트 처리에서 발생 가능한 중복·재시도·상태 꼬임 문제를 재현하고 해결하는 백엔드/DevOps 검증 프로젝트**입니다.

따라서 범위를 명확히 제한하여 프로젝트 완성도를 높이는 것을 우선합니다.

---

## Phase 1 (1차 개발) 범위

### ✅ 포함할 것

#### 거래 이벤트 유형 (3가지)

| 이벤트 | 설명 | 예시 |
|--------|-----|------|
| **DEPOSIT** | 계좌 입금 | 은행에서 송금 완료 알림 |
| **WITHDRAW** | 계좌 출금 | 출금 승인 완료 알림 |
| **CANCEL** | 거래 취소 | 이전 거래의 취소 완료 알림 |

#### 핵심 도메인 엔티티

```
TransactionEvent        거래 이벤트 원본 (외부 시스템에서 받은 데이터)
Account                계좌/사용자 정보 (잔액 보유)
LedgerEntry            회계성 거래 기록 (왜 잔액이 바뀌었는가)
IdempotencyRecord      멱등성 키 기반 요청/응답 기록
EventStateHistory      이벤트 상태 변경 이력
```

#### API 기능

- `POST /api/v1/transaction-events` → 거래 이벤트 수신
- `GET /api/v1/transaction-events/{id}` → 이벤트 상태 조회
- `GET /api/v1/accounts/{id}/balance` → 계좌 잔액 조회
- `GET /api/v1/transaction-events/{id}/histories` → 상태 변경 이력 조회
- `GET /health` → 서버 상태 확인
- `GET /ready` → DB/Redis 준비 상태 확인

#### 정합성 검증 기능

- **Idempotency Key 기반 중복 제거**
- **PostgreSQL Transaction과 Unique Constraint**
- **Redis Lock과 Cache**
- **상태 머신 기반 상태 전이 검증**
- **구조화 로그 및 추적 ID**

#### 테스트 및 DevOps

- Unit Test (상태 머신, 계산 로직)
- Integration Test (API + DB + Redis)
- Consistency Test (중복 이벤트, 동시성)
- k6 기반 부하 테스트 및 장애 재현
- GitHub Actions CI/CD
- Docker Compose 기반 환경
- Prometheus/Grafana 모니터링

---

## ❌ Phase 1에서 제외할 것 (Phase 2 이후)

### 고급 거래 유형

| 기능 | 이유 | 예정 시기 |
|------|------|---------|
| **부분 취소** | 환불 로직 복잡화 → 단순 FULL CANCEL만 | Phase 2 |
| **복합 거래** (A계좌 → B계좌 이체) | 분산 트랜잭션 필요 | Phase 2 |
| **실시간 환율 계산** | 멀티 통화 처리 복잡 | Phase 2 |
| **수수료 계산** | 비즈니스 로직 복잡화 | Phase 2 |

### 외부 시스템 연동

| 기능 | 이유 | 예정 시기 |
|------|------|---------|
| **실제 은행 API 연동** | Mock으로 충분 | Phase 3 |
| **실제 결제 PG 연동** | 테스트 환경에서는 필요 없음 | Phase 3 |
| **실제 증권사 주문 체결** | 단순 DEPOSIT/WITHDRAW로 대체 | Phase 3 |

### 고급 DevOps 기능

| 기능 | 이유 | 예정 시기 |
|------|------|---------|
| **Kubernetes 운영** | Docker Compose로 충분 | Phase 3 |
| **MSA 분리** (결제 서버, 정산 서버) | 모놀리식으로 시작 | Phase 3 |
| **Kafka 기반 이벤트 스트리밍** | 동기식 처리로 충분 | Phase 3 |
| **고급 메시 (Istio)** | 로드 밸런싱만 필요 | Phase 3 |

---

## 1차 개발 도메인 모델 요약

### 기본 흐름

```
외부 시스템
    ↓
POST /api/v1/transaction-events (with Idempotency-Key)
    ↓
Idempotency 검증 (Redis → PostgreSQL)
    ↓
Transaction 시작
    ├─ TransactionEvent INSERT
    ├─ Account ROW LOCK
    ├─ 상태 전이 검증
    ├─ LedgerEntry INSERT
    ├─ Account.balance UPDATE
    └─ IdempotencyRecord 저장
    ↓
Transaction COMMIT
    ↓
응답 반환 (Event ID, 새 잔액, 중복 여부)
```

### 데이터 모델

```
Account
├─ account_id (PK)
├─ balance
└─ created_at

TransactionEvent
├─ event_id (PK)
├─ external_event_id (UNIQUE)
├─ account_id (FK)
├─ event_type (DEPOSIT/WITHDRAW/CANCEL)
├─ amount
├─ status (RECEIVED/VALIDATED/PROCESSING/COMPLETED/FAILED)
└─ created_at

LedgerEntry
├─ ledger_id (PK)
├─ transaction_event_id (UNIQUE)
├─ account_id (FK)
├─ amount
├─ type (DEBIT/CREDIT)
└─ created_at

IdempotencyRecord
├─ idempotency_key (PK)
├─ request_hash
├─ response_body
├─ status (PROCESSING/COMPLETED/FAILED)
└─ created_at

EventStateHistory
├─ history_id (PK)
├─ event_id (FK)
├─ from_status
├─ to_status
└─ changed_at
```

---

## 1차 개발 기간 및 완성도

이 절은 초기 범위 산정 기록이다.
실제 구현은 [개발 로드맵](04-development-roadmap.md)의 Phase 1~10까지 완료된 상태를 기준으로 추적한다.

### 초기 개발 일정 예상

| Phase | 내용 | 기간 |
|-------|-----|------|
| 1차 범위 | 프로젝트 기획, 도메인 모델링, 정합성 핵심 로직, Redis 적용, 테스트 자동화, DevOps 환경, 부하 테스트, 문서 정리 | 약 1개월 |

상세 Phase와 완료 여부는 `docs/04-development-roadmap.md`를 최신 기준으로 삼는다.

### 1차 완성도 목표

```
✅ 문제 정의 및 설계 완료
✅ Idempotency 기반 중복 방지 검증 완료
✅ PostgreSQL Transaction 정합성 검증 완료
✅ Redis 장애 시나리오 재현 완료
✅ 상태 머신 테스트 자동화 완료
✅ k6 부하 테스트 완료
⏳ 정합성 게이트 CI/CD 적용은 Phase 11 범위
✅ Prometheus/Grafana 모니터링 완료
✅ 블로그 시리즈 12편 완료
✅ 포트폴리오 프로젝트로 제출 가능한 상태
```

---

## 의사 결정 기록

### 왜 이 범위로 정했는가?

| 결정 | 이유 |
|------|------|
| **DEPOSIT/WITHDRAW/CANCEL만** | 핵심 정합성 문제를 충분히 재현 가능 |
| **모놀리식 백엔드** | MSA는 프로젝트 목표(정합성 검증)와 무관 |
| **실제 외부 API 없음** | Mock으로 충분하고, 개발 속도 향상 |
| **PostgreSQL + Redis** | 금융 시스템의 가장 일반적인 스택 |
| **Docker Compose** | Kubernetes는 overkill, 개발/테스트용 충분 |

---

## 문서 내용 정리

- **문제 정의** → [docs/01-problem-definition.md](01-problem-definition.md)
- **도메인 범위** ✅ 현재 문서
- **정합성 규칙** → [docs/03-consistency-rules.md](03-consistency-rules.md)
- **개발 로드맵** → [docs/04-development-roadmap.md](04-development-roadmap.md)
