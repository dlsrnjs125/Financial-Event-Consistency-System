# 18편. 금융 사내망 관점에서 관리자 API와 Metrics 접근을 분리하기

## 1. 문제를 어떻게 정의했는가

모든 endpoint를 같은 방식으로 열어두면 운영은 편해 보인다.
하지만 `/metrics`, `/ready`, `/admin/reconciliation` 같은 endpoint는 내부 상태와 장애 정보를 노출할 수 있다.

그래서 외부 금융사 호출 경로와 내부 운영자 접근 경로를 분리하는 접근 제어 모델을 설계했다.

## 2. 접근 경로

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

## 3. endpoint별 정책

| Endpoint | 접근 주체 | 통제 방식 |
|---|---|---|
| `/api/v1/transaction-events` | 외부 금융사 | HMAC + timestamp + idempotency key |
| `/metrics` | Prometheus | 내부 Docker network |
| `/ready` | 배포 시스템/Nginx | 내부 접근 |
| `/admin/reconciliation` | 운영자 | IP allowlist + admin token |
| PostgreSQL | API 서버 | 외부 포트 미노출 |
| Redis | API 서버 | 외부 포트 미노출 |

## 4. DLP 관점의 로그 기준

운영 로그는 장애 추적 도구지만, 민감정보 저장소가 되어서는 안 된다.

| 데이터 | 처리 방식 |
|---|---|
| account_no | masking |
| idempotency_key | masking 또는 hash |
| HMAC signature | 저장 금지 |
| client secret | 저장 금지 |
| request body | 원문 저장 금지 |

## 5. 트레이드오프

접근 제한을 강하게 걸면 운영자가 문제를 확인하기 어려워질 수 있다.
반대로 모든 endpoint를 열어두면 장애 정보와 내부 metric이 외부에 노출될 수 있다.

그래서 endpoint를 public/internal로 나누고, 내부 endpoint도 IP allowlist와 token으로 한 번 더 제한하는 방향이 적절하다.

## 6. 완료 기준

Nginx 설정과 문서가 다음 기준을 만족해야 한다.

- 외부 이벤트 API는 HMAC + rate limit 적용
- `/metrics`는 Prometheus 접근만 허용
- `/ready`는 배포/health check 경로로 제한
- `/admin/*`는 내부 운영자 접근만 허용
- 로그에 raw account number, signature, secret이 남지 않음

## 7. 실제 구현 후 보강할 내용

이 글은 Ops Phase 6 구현 전 설계 초안이다. 구현 후에는 다음 내용을 추가한다.

- access matrix 테스트 결과
- public zone에서 `/metrics` 접근 차단 결과
- monitoring zone에서 `/metrics` 접근 허용 결과
- admin audit log 샘플
- masking/security-log-check 결과
