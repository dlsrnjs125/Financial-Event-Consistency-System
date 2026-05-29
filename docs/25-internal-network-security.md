# Internal Network & Secure Admin Access

## 1. 목적

NAC/VPN/DLP 솔루션 자체를 구현하기보다, 금융 사내망 운영 관점에서 어떤 endpoint를 어떤 주체에게 열어야 하는지 정의한다. 외부 금융사 이벤트 수신 경로와 내부 운영자 경로를 분리하고, metrics/admin endpoint는 내부망에서만 접근 가능하도록 설계한다.

## 2. 접근 모델

```text
[External Financial Partner]
        |
        | HMAC + Rate Limit
        v
[Nginx Public Endpoint]
        |
        v
[Transaction Event API]

[Operator Workstation / VPN 대역]
        |
        | IP allowlist + admin token
        v
[Nginx Internal Endpoint]
        |
        v
[/ready, /metrics, /admin/reconciliation]
```

## 3. 접근 정책

| Endpoint | 접근 주체 | 통제 방식 |
|---|---|---|
| `/api/v1/transaction-events` | 외부 금융사 | HMAC + timestamp + idempotency key |
| `/metrics` | Prometheus | 내부 Docker network만 허용 |
| `/ready` | 배포 시스템/Nginx | 내부 접근만 허용 |
| `/admin/reconciliation` | 운영자 | IP allowlist + 관리자 토큰 |
| DB | API 서버 | 외부 포트 미노출 |
| Redis | API 서버 | 외부 포트 미노출 |

## 4. 로그/DLP 기준

| 데이터 | 처리 방식 |
|---|---|
| account_no | 앞/뒤 일부만 노출 또는 masking |
| idempotency_key | hash 또는 masking |
| HMAC signature | 저장 금지 |
| client secret | 저장 금지 |
| request body | 금액/상태 중심으로 제한 저장 |

## 5. README 요약 문장

NAC/VPN/DLP 솔루션 자체를 구현하기보다, 금융 사내망 운영 관점에서 어떤 endpoint를 어떤 주체에게 열어야 하는지 정의한다. 외부 금융사 이벤트 수신 경로와 내부 운영자 경로를 분리하고, metrics/admin endpoint는 내부망에서만 접근 가능하도록 Nginx 정책을 설계한다.
