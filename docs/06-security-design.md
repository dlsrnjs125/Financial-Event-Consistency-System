# 06. Security Design

## 1. 보안 설계 목적

이 시스템은 외부 금융 시스템에서 거래 이벤트를 수신하는 API를 제공한다.

거래 이벤트는 입금, 출금, 취소와 같이 금전 상태에 직접 영향을 줄 수 있으므로 단순히 요청 Body가 올바른지만 검증해서는 안 된다.

보안 설계의 목적은 다음과 같다.

1. 허용된 외부 시스템만 이벤트를 전송할 수 있게 한다.
2. 요청 Body가 중간에 변조되지 않았는지 검증한다.
3. 동일 요청의 재전송과 악의적인 재사용을 구분한다.
4. Idempotency-Key를 통해 중복 요청을 안전하게 처리한다.
5. 로그와 모니터링 과정에서 민감정보가 노출되지 않도록 한다.
6. Secret은 코드와 저장소에서 분리한다.

---

## 2. 외부 시스템 인증 방식

이 프로젝트의 이벤트 수신 API는 일반 사용자가 호출하는 API가 아니라 외부 은행, 결제, 증권 시스템이 호출하는 System-to-System API로 가정한다.

따라서 사용자 로그인용 JWT보다 외부 시스템 인증에 적합한 방식을 사용한다.

### 고려한 방식

| 방식 | 장점 | 한계 |
|------|------|------|
| API Key | 구현이 단순함 | Key 탈취 시 요청 위조 가능 |
| HMAC Signature | 요청 변조 검증 가능 | 클라이언트/서버 간 서명 규칙 공유 필요 |
| JWT | 사용자 인증에 적합 | 시스템 간 요청 Body 변조 검증에는 부족 |
| OAuth2 Client Credentials | 표준적이고 확장성 있음 | Phase 1에서는 구현 복잡도 증가 |
| mTLS | 강한 상호 인증 | 로컬 검증 환경에서는 운영 복잡도 높음 |

### 선택한 방식

Phase 7에서는 `POST /api/v1/transaction-events`에 HMAC Signature 검증을 적용한다.
이 API는 일반 사용자 로그인 API가 아니라 외부 금융 시스템이 호출하는 System-to-System API다.

```text
X-Client-Id: bank-a
X-Timestamp: 2026-05-27T10:00:00+09:00
X-Signature: hmac-sha256-signature
Idempotency-Key: idem-20260527-0001
```

---

## 3. HMAC Signature 검증

### 서명 대상

서명 대상은 다음 값을 조합한다.

```text
HTTP_METHOD + PATH + TIMESTAMP + REQUEST_BODY_HASH
```

예시:

```text
POST
/api/v1/transaction-events
2026-05-27T10:00:00+09:00
SHA256(request_body)
```

서버는 `X-Client-Id`를 기준으로 해당 외부 시스템의 Secret을 조회한 뒤 동일한 방식으로 Signature를 생성하고, 요청 Header의 `X-Signature`와 비교한다.

Phase 7 구현 기준의 canonical base string은 다음 형식이다.

```text
{HTTP_METHOD}
{PATH}
{X_TIMESTAMP 원문}
{SHA256(raw_request_body)}
```

예:

```text
POST
/api/v1/transaction-events
2026-05-27T10:00:00+09:00
<sha256-body-hash>
```

검증 시 `hmac.compare_digest`를 사용해 timing attack 위험을 줄인다.
Query string은 서명 대상에서 제외하며, `PATH`는 URL path만 사용한다.
Body hash는 FastAPI/Pydantic parsing 이후 값이 아니라 raw request body bytes 기준으로 계산한다.

---

## 4. Replay Attack 방지

HMAC Signature만으로는 과거에 정상적으로 생성된 요청이 다시 전송되는 것을 완전히 막기 어렵다.

따라서 다음 정책을 적용한다.

### Timestamp 검증

`X-Timestamp`는 서버 현재 시각 기준 `+-5분` 이내여야 한다.

허용 범위를 벗어난 요청은 `401 Unauthorized`로 거부한다.

### Idempotency-Key 검증

동일 요청이 다시 들어오는 경우에는 Idempotency-Key를 기준으로 기존 처리 결과를 반환한다.

다만 같은 Idempotency-Key로 다른 요청 Body가 들어오면 재시도가 아니라 충돌로 판단하고 `409 Conflict`를 반환한다.

### Nonce 도입 여부

Phase 7에서는 별도 Nonce 저장소를 두지 않는다.

대신 다음 조합으로 Replay 위험을 줄인다.

```text
HMAC Signature + Timestamp 제한 + Idempotency-Key + request_hash 검증
```

추후 보안 수준을 높이는 Phase에서는 nonce 또는 signature_id를 저장해 동일 서명 재사용을 차단할 수 있다.

---

## 5. Idempotency-Key 검증 정책

Idempotency-Key는 중복 요청을 안전하게 처리하기 위한 필수 Header다.

```text
Idempotency-Key: idem-20260527-0001
```

### 검증 규칙

| 상황 | 처리 |
|------|------|
| Idempotency-Key 없음 | 400 Bad Request |
| 새로운 Key | 신규 처리 |
| 같은 Key + 같은 Body | 기존 응답 반환 |
| 같은 Key + 다른 Body | 409 Conflict |
| 같은 Key + 처리 중 | 202 Accepted |
| 같은 Key + 처리 완료 | 200 OK, 기존 결과 반환 |

### request_hash 저장

동일 Idempotency-Key로 다른 요청이 들어오는 것을 막기 위해 요청 Body를 정규화한 뒤 Hash로 저장한다.

```text
request_hash = SHA256(normalized_request_body)
```

저장 항목:

- `idempotency_key`
- `request_hash`
- `response_body`
- `status`
- `created_at`
- `expires_at`

---

## 6. 로그 마스킹 정책

거래 이벤트 처리 시스템에서는 장애 분석을 위해 충분한 로그가 필요하다.

하지만 금융 정보와 Secret이 로그에 노출되면 보안 사고로 이어질 수 있다.

### 로그에 남겨도 되는 값

- `trace_id`
- `request_id`
- `event_id`
- `external_event_id`
- `idempotency_key`
- `event_type`
- `status_before`
- `status_after`
- `latency_ms`
- `result_code`

### 마스킹이 필요한 값

| 값 | 처리 방식 |
|----|-----------|
| `account_no` | 뒤 4자리만 노출 |
| `user_id` | 내부 식별자 또는 hash |
| `amount` | 도메인 판단에 필요하면 남기되 접근 제한 |
| `client_id` | 허용 |
| `signature` | 원문 저장 금지 |
| access token | 저장 금지 |
| refresh token | 저장 금지 |
| API secret | 저장 금지 |

계좌번호 마스킹 예시:

```text
1234567890123 -> *********0123
```

---

## 7. Secret 관리

Phase 7에서는 Secret Manager나 Vault 연동 대신 env 기반 `ClientSecretProvider`로 시작한다.

```text
EXTERNAL_CLIENT_SECRETS=bank-a:change-me-secret,broker-b:change-me-secret
```

이 값은 로컬/테스트용 더미 예시이며, 실제 운영 secret은 GitHub Secrets, Secret Manager, Vault 등 저장소 밖의 안전한 경로로 주입해야 한다.
Secret rotation 자동화와 Secret Manager 연동은 후속 Phase 또는 별도 ADR에서 다룬다.

### 저장소에 포함하지 않는 값

- `.env`
- `.env.local`
- `.env.production`
- `*.pem`
- `id_rsa`
- `API_SECRET`
- `JWT_SECRET_KEY`
- `DB_PASSWORD`
- `REDIS_PASSWORD`

### 저장소에 포함하는 값

- `.env.example`
- `.env.local.example`
- `.env.test.example`

### GitHub Secrets 사용 값

- `DB_HOST`
- `DB_USER`
- `DB_PASSWORD`
- `REDIS_URL`
- `JWT_SECRET_KEY`
- `EXTERNAL_CLIENT_SECRET`
- `SSH_HOST`
- `SSH_USER`
- `SSH_PRIVATE_KEY`
- `DOCKER_REGISTRY_USERNAME`
- `DOCKER_REGISTRY_PASSWORD`

### `.gitignore` 기준

```gitignore
.env
.env.*
!.env.example
!.env.local.example
!.env.test.example
*.pem
id_rsa
```

---

## 8. OWASP API Security 기준 점검

| 항목 | 적용 방식 |
|------|-----------|
| Broken Object Level Authorization | 다른 계좌/이벤트 조회 제한 |
| Broken Authentication | API Key + HMAC Signature 검증 |
| Broken Object Property Level Authorization | 요청 Body 허용 필드만 처리 |
| Unrestricted Resource Consumption | Rate Limit, Timeout, Body Size 제한 |
| Broken Function Level Authorization | 관리자/운영자 API 분리 |
| Unrestricted Access to Sensitive Business Flows | 동일 이벤트 폭주 방지, Idempotency 적용 |
| Server Side Request Forgery | 외부 URL 입력 기능 제외 |
| Security Misconfiguration | DEBUG 비활성화, CORS 제한 |
| Improper Inventory Management | OpenAPI 문서로 API 목록 관리 |
| Unsafe Consumption of APIs | 외부 시스템 요청 Body 신뢰 금지 |

---

## 9. 설계 결론

이 프로젝트의 보안 설계는 단순 인증을 넘어서 거래 이벤트가 안전하게 수신되고, 변조와 재전송 위험을 줄이며, 민감정보가 로그와 저장소에 노출되지 않도록 하는 데 초점을 둔다.

Phase 7에서는 HMAC Signature로 외부 시스템 인증과 요청 변조 여부를 검증하고, Idempotency-Key와 request_hash 검증으로 중복 요청과 충돌 요청을 구분한다.
HMAC은 Idempotency를 대체하지 않으며, Idempotency는 계속 중복 처리의 기준이다.
