# 15. API Contract

## 1. 목적

이 문서는 외부 금융 시스템과 API 서버 사이의 요청/응답 계약을 정의한다.

구현 단계에서는 이 문서를 Pydantic Schema, OpenAPI 문서, API 테스트 fixture의 기준으로 사용한다.

---

## 2. POST /api/v1/transaction-events

거래 이벤트를 수신한다.

### Headers

| name | required | description |
|------|----------|-------------|
| `X-Client-Id` | true | 외부 시스템 ID |
| `X-Timestamp` | true | 요청 생성 시각 |
| `X-Signature` | true | HMAC Signature |
| `Idempotency-Key` | true | 멱등성 키 |

### Request Body

```json
{
  "external_event_id": "BANK-A-20260527-0001",
  "account_no": "1234567890",
  "event_type": "DEPOSIT",
  "amount": 10000,
  "currency": "KRW",
  "occurred_at": "2026-05-27T10:00:00+09:00"
}
```

CANCEL 요청은 원거래 식별을 위해 `original_external_event_id`가 필수다.
DEPOSIT/WITHDRAW 요청에서는 이 필드를 사용하지 않는다.

```json
{
  "external_event_id": "BANK-A-20260527-CANCEL-0001",
  "account_no": "1234567890",
  "event_type": "CANCEL",
  "amount": 10000,
  "currency": "KRW",
  "occurred_at": "2026-05-27T10:10:00+09:00",
  "original_external_event_id": "BANK-A-20260527-0001"
}
```

### Success Response

```json
{
  "event_id": "evt-0001",
  "external_event_id": "BANK-A-20260527-0001",
  "status": "COMPLETED",
  "processed": true,
  "duplicated": false,
  "balance_after": 150000
}
```

### Duplicate Response

```json
{
  "event_id": "evt-0001",
  "external_event_id": "BANK-A-20260527-0001",
  "status": "COMPLETED",
  "processed": false,
  "duplicated": true,
  "balance_after": 150000
}
```

### Processing Response

```json
{
  "status": "PROCESSING",
  "message": "The same request is already being processed.",
  "retry_after_seconds": 3
}
```

### Error Response

```json
{
  "status": "error",
  "code": "IDEMPOTENCY_CONFLICT",
  "message": "The same Idempotency-Key was used with a different request body."
}
```

---

## 3. GET /api/v1/transaction-events/{event_id}

거래 이벤트 상태를 조회한다.

### Response

```json
{
  "event_id": "evt-0001",
  "external_event_id": "BANK-A-20260527-0001",
  "event_type": "DEPOSIT",
  "status": "COMPLETED",
  "amount": 10000,
  "currency": "KRW",
  "occurred_at": "2026-05-27T10:00:00+09:00",
  "created_at": "2026-05-27T10:00:01+09:00"
}
```

---

## 4. GET /api/v1/accounts/{account_no}/balance

계좌 현재 잔액을 조회한다.

### Response

```json
{
  "account_no": "********7890",
  "balance": 150000,
  "currency": "KRW",
  "as_of": "2026-05-27T10:00:01+09:00"
}
```

---

## 5. HTTP Status 기준

상세 기준은 [11-api-response-policy.md](11-api-response-policy.md)를 따른다.

| status | meaning |
|--------|---------|
| 200 OK | 신규 처리 성공 또는 기존 결과 반환 |
| 202 Accepted | 동일 요청이 처리 중 |
| 400 Bad Request | 필수 Header 또는 Body 누락 |
| 401 Unauthorized | 인증 실패 또는 Signature 검증 실패 |
| 403 Forbidden | 허용되지 않은 client |
| 409 Conflict | 같은 Idempotency-Key로 다른 Body 요청 |
| 422 Unprocessable Entity | 도메인 규칙 위반 |
| 503 Service Unavailable | 일시적 처리 불가 |

---

## 6. 설계 결론

API Contract는 외부 시스템의 재시도 전략과 서버의 정합성 처리 방식을 연결하는 기준이다.

요청 Header, Body, 응답 구조, HTTP Status를 구현 전에 고정해두면 API 구현, 테스트, OpenAPI 문서가 같은 기준을 공유할 수 있다.

Phase 5에서는 HMAC 관련 Header(`X-Client-Id`, `X-Timestamp`, `X-Signature`)를 아직 검증하지 않고, `Idempotency-Key`만 필수로 검증한다.
