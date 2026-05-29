# Ops Phase 2 - Nginx Reverse Proxy & Internal Access Control

## 1. 해결하려는 운영 문제

Nginx는 단순 reverse proxy가 아니라 금융 이벤트 시스템의 첫 번째 운영 통제 지점이다.

외부 금융사 이벤트 수신 API와 내부 운영자/모니터링 endpoint를 같은 방식으로 열어두면 보안과 운영 경계가 흐려진다.

Ops Phase 2는 public endpoint와 internal endpoint를 분리하고, Nginx와 API의 책임을 명확히 나눈다.

## 2. 구현 범위

### 역할 분리

| 계층 | 담당 정책 | 예시 |
|---|---|---|
| Nginx | 네트워크 접근 제어, rate limit, request_id 부여, internal endpoint 보호 | `/metrics` 외부 차단, `/api` rate limit |
| API | HMAC 검증, timestamp 검증, idempotency 검증, business validation | signature invalid, replay attack 차단 |
| DB | 최종 정합성 보장 | unique constraint, transaction |
| Redis | 중복 요청 완화 | lock/cache/fallback |

### Endpoint 분리

Public endpoint:

- `POST /api/v1/transaction-events`
- `GET /health`

Internal endpoint:

- `GET /ready`
- `GET /metrics`
- `GET /admin/reconciliation`
- `GET /admin/consistency-check`

## 3. 제외 범위

- WAF 제품 도입은 제외한다.
- mTLS 인증은 초기 로컬 설계 범위에서 제외한다.
- 실제 사내 VPN/NAC 연동은 제외한다.
- 관리자 API의 세부 business 기능 구현은 별도 Phase로 분리한다.

## 4. 파일/디렉터리 변경 계획

```text
infra/
  nginx/
    nginx.conf
    conf.d/
      api.conf
      admin.conf
      rate-limit.conf
      security-headers.conf
      metrics-access.conf

scripts/
  nginx/
    check-nginx-config.sh
    test-rate-limit.sh
    test-internal-access.sh
    check-log-format.sh
```

## 5. 검증 명령어

```bash
make nginx-test
make nginx-public-api-test
make nginx-internal-deny-test
make rate-limit-test
make nginx-log-format-test
```

성공 기준:

- 외부에서 `/api/v1/transaction-events` 접근 가능
- 외부에서 `/metrics` 접근 시 403 또는 404
- Prometheus network에서 `/metrics` 접근 가능
- rate limit 초과 시 429 반환
- Nginx log에 `request_id`, `upstream_response_time` 포함
- HMAC signature, raw account number, raw request body 미포함

## 6. 완료 기준과 README에 남길 결과

### Access Log Format

```nginx
log_format financial_json escape=json
  '{'
  '"time":"$time_iso8601",'
  '"remote_addr":"$remote_addr",'
  '"request_id":"$request_id",'
  '"trace_id":"$http_x_trace_id",'
  '"method":"$request_method",'
  '"uri":"$uri",'
  '"status":$status,'
  '"request_time":$request_time,'
  '"upstream_response_time":"$upstream_response_time",'
  '"upstream_addr":"$upstream_addr",'
  '"user_agent":"$http_user_agent"'
  '}';
```

### 기록 금지

- HMAC signature
- raw request body
- account_no 원문
- authorization header
- idempotency key 원문

### 기록 허용

- trace_id
- request_id
- masked account_no
- hashed idempotency_key
- status
- latency
- upstream

README에는 다음 결과를 남긴다.

- Nginx public/internal endpoint 분리 완료
- `/metrics`, `/ready`, `/admin/*` 외부 접근 차단 확인
- rate limit 초과 시 429 반환 확인
- Nginx JSON access log에 trace/request/upstream latency 기록 확인
