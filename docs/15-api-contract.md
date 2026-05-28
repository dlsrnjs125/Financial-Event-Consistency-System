# 15. API Contract

## 1. 목적

이 문서는 외부 금융 시스템과 API 서버 사이의 요청/응답 계약을 정의한다.

구현 단계에서는 이 문서를 Pydantic Schema, OpenAPI 문서, API 테스트 fixture의 기준으로 사용한다.

---

## 2. POST /api/v1/transaction-events

거래 이벤트를 수신한다.

### Headers

Phase 7부터 `POST /api/v1/transaction-events`는 아래 Header를 실제로 검증한다.

| name | required | description |
|------|----------|-------------|
| `X-Client-Id` | true | 외부 시스템 ID |
| `X-Timestamp` | true | 요청 생성 시각 |
| `X-Signature` | true | HMAC Signature |
| `Idempotency-Key` | true | 멱등성 키 |

Signature base string은 반드시 LF newline(`\n`)으로 구분한다.
공백 연결이나 단순 문자열 덧붙이기가 아니라 아래 네 줄을 `\n`으로 join한 문자열이다.

```text
{HTTP_METHOD_UPPERCASE}\n{PATH_WITHOUT_QUERY}\n{X_TIMESTAMP_HEADER_VALUE}\n{SHA256_RAW_REQUEST_BODY}
```

논리적 줄 구조:

```text
{HTTP_METHOD_UPPERCASE}
{PATH_WITHOUT_QUERY}
{X_TIMESTAMP_HEADER_VALUE}
{SHA256_RAW_REQUEST_BODY}
```

예:

```text
POST
/api/v1/transaction-events
2026-05-27T10:00:00+09:00
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

`X-Signature`는 위 base string을 client secret으로 HMAC-SHA256 서명한 64-character hex digest다.
`sha256=<digest>` prefix 형식은 Phase 7에서 지원하지 않는다.
Hex digest는 대소문자를 구분하지 않고 비교 전에 lowercase로 정규화한다.
Query string은 서명 대상에서 제외한다.

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

Phase 7에서는 HMAC 필수 검증을 거래 이벤트 생성 API에 우선 적용한다.
조회 API의 외부 공개 여부와 권한 모델은 후속 Phase 또는 별도 ADR에서 다룬다.

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

Phase 7에서는 `POST /api/v1/transaction-events`에서 HMAC 관련 Header(`X-Client-Id`, `X-Timestamp`, `X-Signature`)와 `Idempotency-Key`를 모두 검증한다.
Phase 7은 KRW 정수 원 단위를 기준으로 `amount`와 `balance_after`를 JSON number로 반환한다.
거래 처리 중 도메인 실패가 발생하면 Idempotency 실패 응답 재사용을 위해 TransactionEventService가 표준 실패 body를 저장하고 해당 HTTP status로 반환한다.
