# Nginx Reverse Proxy & Internal Access Control

## 1. 목적

Nginx를 단순 reverse proxy가 아니라 금융 이벤트 시스템의 첫 번째 운영 통제 지점으로 설계한다. 외부 금융사 이벤트 수신 경로와 내부 운영자/모니터링 경로를 분리하고, endpoint별 접근 정책을 다르게 적용한다.

## 2. 설정 구조

```text
infra/nginx/
  nginx.conf
  conf.d/
    api.conf
    admin.conf
    rate-limit.conf
    security-headers.conf
```

## 3. 접근 정책

| Endpoint | 접근 주체 | 통제 방식 |
|---|---|---|
| `/api/v1/transaction-events` | 외부 금융사 | HMAC + timestamp + rate limit |
| `/metrics` | Prometheus | 내부 Docker network만 허용 |
| `/ready` | 배포 시스템/Nginx | 내부 접근 중심 |
| `/admin/*` | 운영자 | IP allowlist + admin token |

## 4. Nginx 로그

Nginx access log에는 다음 값을 포함한다.

- `trace_id`
- `request_id`
- `upstream_response_time`
- `status`
- `request_time`
- `upstream_addr`

원문 account number, HMAC signature, raw body는 기록하지 않는다.

## 5. 완료 기준

```bash
make nginx-test
make rate-limit-test
make admin-access-test
```

## 6. README 요약 문장

Nginx를 단순 라우팅 계층이 아니라 금융 이벤트 시스템의 첫 번째 운영 통제 지점으로 정의한다. 외부 금융사 이벤트 수신 API에는 rate limit과 HMAC 인증을 적용하고, 관리자/metrics/ready endpoint는 내부 접근만 허용하도록 분리한다.
