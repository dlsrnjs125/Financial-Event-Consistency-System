# 11. API Response and Retry Policy

## 1. 목적

외부 금융 시스템은 네트워크 지연, 타임아웃, 5xx 응답을 기준으로 동일 이벤트를 재시도할 수 있다.

따라서 API는 각 상황에 대해 명확한 HTTP Status를 반환해야 한다.

---

## 2. HTTP 응답 정책

| 상황 | HTTP Status | 의미 | 재시도 가능 여부 |
|------|-------------|------|------------------|
| 신규 처리 성공 | 200 OK | 처리 완료 | 불필요 |
| 동일 요청 재전송 | 200 OK | 기존 결과 반환 | 불필요 |
| 처리 중 재요청 | 202 Accepted | 처리 중 | 일정 시간 후 재조회 |
| 같은 Key 다른 Body | 409 Conflict | 충돌 요청 | 재시도해도 실패 |
| Idempotency-Key 누락 | 400 Bad Request | 필수 Header 누락 | Header 추가 후 재요청 |
| 잘못된 상태 전이 | 422 Unprocessable Entity | 도메인 규칙 위반 | 재시도해도 실패 |
| DB Pool 고갈 | 503 Service Unavailable | 일시적 처리 불가 | 가능 |
| Redis 장애 | 기존 DB 처리 결과 | PostgreSQL 기반 fallback | 상황별 |
| 인증 실패 | 401 Unauthorized | 인증 실패 | Secret 확인 필요 |
| 권한 없음 | 403 Forbidden | 허용되지 않은 client | 재시도해도 실패 |
| 요청 형식 오류 | 400 Bad Request | 필수 필드 누락 | 수정 후 재요청 |

---

## 3. 처리 중 재요청 정책

동일 Idempotency-Key가 이미 PROCESSING 상태라면 다음 응답을 반환한다.

```http
202 Accepted
```

응답 Body:

```json
{
  "status": "PROCESSING",
  "message": "The same request is already being processed.",
  "retry_after_seconds": 3
}
```

## 4. Idempotency 재요청 정책

Phase 4에서는 실제 거래 처리 API가 아니라 Idempotency 판단 기반만 구현한다.

| 상황 | 처리 정책 |
|------|-----------|
| Idempotency-Key Header 없음 | `400 Bad Request`로 매핑 |
| 같은 Key + 같은 Body + PROCESSING | `202 Accepted`로 매핑 |
| 같은 Key + 같은 Body + COMPLETED | 저장된 `response_code`, `response_body` 재사용 |
| 같은 Key + 같은 Body + FAILED | Phase 4 기준 저장된 실패 응답 재사용 |
| 같은 Key + 다른 Body | `409 Conflict`로 매핑 |

FAILED 재처리 허용 여부는 후속 ADR에서 별도 검토한다.
`expires_at`은 Phase 4에서 보관 정책 기준으로만 사용하며, 요청 처리 중 기존 Idempotency-Key를 자동으로 무효화하지 않는다.
만료 삭제는 별도 운영 작업 또는 배치에서 수행한다.
완료/실패 결과 저장은 `PROCESSING -> COMPLETED`, `PROCESSING -> FAILED`만 허용한다.
이미 `COMPLETED` 또는 `FAILED`인 요청에 같은 결과 저장이 다시 호출되면 기존 응답을 유지한다.

---

## 5. Phase 6 Redis Lock/Cache 응답 정책

Phase 6에서는 Redis를 최종 정합성 저장소가 아니라 중복 요청 폭주 완화와 완료 응답 재사용을 위한 최적화 계층으로 사용한다.

| 상황 | 처리 정책 |
|------|-----------|
| Redis Cache hit + 같은 request_hash | DB 조회 없이 저장된 `response_code`, `response_body` 반환 |
| Redis Cache hit + 다른 request_hash | Cache를 사용하지 않고 DB IdempotencyRecord로 fallback |
| Redis Cache miss | 기존 DB IdempotencyService로 fallback |
| DB에서 COMPLETED 재사용 확인 | Redis Cache 저장을 best-effort로 시도 |
| Redis Lock 획득 실패 | DB transaction 진입 전 `202 Accepted` 처리 중 응답 반환 |
| Redis Lock 획득 성공 | 기존 DB Transaction 기반 거래 처리 수행 후 finally에서 release |
| Redis 장애 또는 timeout | Redis Lock/Cache 없이 기존 DB 기반 처리로 fallback |

Redis Lock 획득 실패는 거래 실패가 아니라 "동일 Idempotency-Key 요청이 이미 처리 중일 가능성이 높다"는 신호로 다룬다.
Redis 장애가 발생해도 PostgreSQL Unique Constraint와 DB Transaction을 최종 방어선으로 유지한다.

---

## 6. 설계 결론

HTTP Status는 단순 성공/실패 표현이 아니라 외부 시스템의 재시도 전략에 영향을 준다.

따라서 재시도 가능한 실패와 재시도해도 의미 없는 실패를 명확히 구분한다.
