# 12. Data Model Specification

## 1. 목적

이 문서는 SQLAlchemy ORM 모델과 Alembic Migration을 작성하기 위한 컬럼 단위 기준을 정의한다.

도메인 문서와 ERD가 엔티티의 의미와 관계를 설명한다면, 이 문서는 실제 구현에서 사용할 테이블, 컬럼, 제약조건, 타입을 고정한다.

금액은 부동소수점 오차를 피하기 위해 정수 단위로 저장한다. Phase 2에서는 KRW 기준 최소 통화 단위를 원으로 보고 `bigint`를 사용한다.

모든 시각 컬럼은 외부 금융 시스템 발생 시각과 내부 처리 시각을 비교할 수 있도록 timezone-aware timestamp로 저장한다.

---

## 2. accounts

계좌의 현재 상태를 저장한다.

| column | type | constraint | description |
|--------|------|------------|-------------|
| `id` | bigint | PK | 내부 계좌 ID |
| `account_no` | varchar(64) | UNIQUE, NOT NULL | 마스킹 대상 계좌번호 |
| `balance` | bigint | NOT NULL, default 0 | 현재 잔액 |
| `status` | varchar(20) | NOT NULL, default ACTIVE | ACTIVE, LOCKED, CLOSED |
| `created_at` | timestamptz | NOT NULL | 생성 시각 |
| `updated_at` | timestamptz | NOT NULL | 수정 시각 |

### 제약조건

- `account_no`는 외부 요청에서 전달되는 계좌번호이며 로그에서는 마스킹한다.
- `balance`는 빠른 조회를 위한 현재 잔액이다.
- 정합성 검증과 감사 기준은 `ledger_entries`를 우선한다.
- `status = LOCKED` 또는 `CLOSED` 상태에서는 신규 거래 처리를 제한한다.

---

## 3. transaction_events

외부 금융 시스템에서 수신한 거래 이벤트를 저장한다.

| column | type | constraint | description |
|--------|------|------------|-------------|
| `id` | bigint | PK | 내부 이벤트 ID |
| `external_event_id` | varchar(128) | UNIQUE, NOT NULL | 외부 시스템 이벤트 ID |
| `idempotency_key` | varchar(128) | NOT NULL | 멱등성 키 |
| `account_id` | bigint | FK, NOT NULL | 대상 계좌 |
| `event_type` | varchar(20) | NOT NULL | DEPOSIT, WITHDRAW, CANCEL |
| `amount` | bigint | NOT NULL | 거래 금액 |
| `currency` | varchar(10) | NOT NULL, default KRW | 통화 코드 |
| `status` | varchar(30) | NOT NULL | 이벤트 상태 |
| `occurred_at` | timestamptz | NOT NULL | 외부 시스템 발생 시각 |
| `created_at` | timestamptz | NOT NULL | 수신 시각 |
| `updated_at` | timestamptz | NOT NULL | 수정 시각 |

### 제약조건

- `external_event_id`는 동일 이벤트 중복 수신을 막는 최종 방어선이다.
- `idempotency_key`는 요청 재시도와 충돌 요청을 구분하는 기준이다.
- Phase 2에서는 `currency = KRW`를 기본값으로 사용하되, 외부 API 요청의 통화 코드를 명시적으로 보관한다.
- 동일 `idempotency_key`에 다른 요청 Body가 들어오면 `409 Conflict`로 처리한다.
- `status` 값은 [13-state-transition-table.md](13-state-transition-table.md)의 상태 전이표를 따른다.

---

## 4. ledger_entries

잔액 변경의 근거가 되는 원장 기록을 저장한다.

| column | type | constraint | description |
|--------|------|------------|-------------|
| `id` | bigint | PK | 원장 ID |
| `transaction_event_id` | bigint | UNIQUE, FK | 연결된 이벤트 |
| `account_id` | bigint | FK, NOT NULL | 계좌 ID |
| `entry_type` | varchar(20) | NOT NULL | CREDIT, DEBIT |
| `amount` | bigint | NOT NULL | 원장 반영 금액 |
| `balance_after` | bigint | NOT NULL | 반영 후 잔액 |
| `created_at` | timestamptz | NOT NULL | 생성 시각 |

### 제약조건

- 하나의 `transaction_event_id`는 하나의 `ledger_entries` row와만 연결된다.
- `entry_type = CREDIT`이면 잔액 증가, `entry_type = DEBIT`이면 잔액 감소를 의미한다.
- CANCEL 이벤트는 원거래를 삭제하지 않고 반대 방향 LedgerEntry를 생성한다.
- 감사와 Reconciliation 기준은 `ledger_entries`다.

---

## 5. idempotency_records

Idempotency-Key 기반 요청 처리 결과를 저장한다.

| column | type | constraint | description |
|--------|------|------------|-------------|
| `id` | bigint | PK | 내부 ID |
| `idempotency_key` | varchar(128) | UNIQUE, NOT NULL | 멱등성 키 |
| `request_hash` | varchar(64) | NOT NULL | 정규화된 요청 Body의 SHA256 hash |
| `status` | varchar(30) | NOT NULL | PROCESSING, COMPLETED, FAILED |
| `response_code` | integer | nullable | 완료 또는 실패 응답의 HTTP status code |
| `response_body` | jsonb | nullable | 완료된 요청의 응답 Body |
| `error_message` | text | nullable | 실패 사유 |
| `created_at` | timestamptz | NOT NULL | 생성 시각 |
| `updated_at` | timestamptz | NOT NULL | 수정 시각 |
| `completed_at` | timestamptz | nullable | 완료 시각 |
| `locked_until` | timestamptz | nullable | 처리 중 재요청 제어를 위한 잠금 만료 시각 |
| `expires_at` | timestamptz | nullable | 보관 만료 시각 |

### 제약조건

- 같은 `idempotency_key`와 같은 `request_hash`는 기존 응답을 반환한다.
- 같은 `idempotency_key`와 다른 `request_hash`는 충돌로 처리한다.
- PROCESSING 상태 요청이 다시 들어오면 `202 Accepted`를 반환한다.
- `response_code`와 `response_body`는 동일 Idempotency-Key 재요청 시 기존 응답을 재사용하기 위한 값이다.
- `updated_at`은 PROCESSING, COMPLETED, FAILED 상태 변경 추적에 사용한다.
- `locked_until`은 DB 기반 처리 중 상태 확인 또는 Redis Lock 장애 시 보조 판단 기준으로 사용할 수 있다.
- Phase 4에서 `expires_at`은 보관 정책 기준이며, 요청 처리 중 자동 무효화 기준으로 사용하지 않는다.
- `PROCESSING -> COMPLETED`, `PROCESSING -> FAILED`만 결과 저장 전이로 허용한다.
- 이미 `COMPLETED` 또는 `FAILED`인 record에 같은 결과 저장이 다시 호출되면 기존 값을 유지한다.
- 만료 삭제 대상은 `COMPLETED`, `FAILED` record로 제한한다. `PROCESSING` 만료 record는 후속 복구/실패 처리 정책 없이 삭제하지 않는다.

---

## 6. event_state_histories

거래 이벤트 상태 변경 이력을 저장한다.

| column | type | constraint | description |
|--------|------|------------|-------------|
| `id` | bigint | PK | 상태 이력 ID |
| `transaction_event_id` | bigint | FK, NOT NULL | 연결된 이벤트 |
| `old_status` | varchar(30) | nullable | 이전 상태 |
| `new_status` | varchar(30) | NOT NULL | 변경 후 상태 |
| `reason` | varchar(255) | nullable | 상태 변경 사유 |
| `created_at` | timestamptz | NOT NULL | 생성 시각 |

### 제약조건

- 상태 변경은 append-only로 기록한다.
- `old_status`가 null이면 최초 상태 기록을 의미한다.
- 허용되지 않은 상태 전이는 기록 전에 차단한다.

---

## 7. 설계 결론

이 데이터 모델의 핵심은 `transaction_events`, `ledger_entries`, `idempotency_records`의 유일성 제약으로 중복 반영을 차단하는 것이다.

`account.balance`는 조회 성능을 위한 현재 상태이며, 거래 정합성과 감사 가능성은 Ledger와 상태 이력으로 검증한다.
