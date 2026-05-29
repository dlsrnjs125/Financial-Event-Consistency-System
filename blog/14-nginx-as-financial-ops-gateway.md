# 14편. Nginx를 금융 이벤트 시스템의 운영 관문으로 설계하기

## 1. 문제를 어떻게 정의했는가

Phase 12까지 Nginx는 Blue-Green traffic switch 역할을 했다. 하지만 금융 이벤트 시스템에서 Nginx는 단순 reverse proxy보다 더 큰 의미를 가진다. 외부 금융사 요청과 내부 운영자 요청이 같은 통로로 들어오면, 운영 편의성은 높아질 수 있지만 보안과 장애 대응 기준은 흐려진다.

그래서 Nginx를 첫 번째 운영 통제 지점으로 정의했다.

```text
외부 금융사 -> public endpoint -> transaction event API
운영자/VPN -> internal endpoint -> ready/metrics/admin
Prometheus -> internal network -> metrics
```

## 2. 외부 API와 내부 API를 나누는 이유

`POST /api/v1/transaction-events`는 외부 금융사가 호출하는 endpoint다. HMAC, timestamp, idempotency key, rate limit이 중요하다.

반대로 `/metrics`, `/ready`, `/admin/reconciliation`은 운영자가 시스템 상태를 확인하기 위한 endpoint다. 이 endpoint를 외부에 그대로 열면 내부 상태, metric 이름, 장애 정보를 노출할 수 있다.

따라서 endpoint는 기능이 아니라 접근 주체 기준으로 나눠야 한다.

| Endpoint | 접근 주체 | 정책 |
|---|---|---|
| Transaction Event API | 외부 금융사 | HMAC + rate limit |
| Metrics | Prometheus | 내부 network |
| Ready | 배포 시스템/Nginx | 제한 접근 |
| Admin | 운영자 | IP allowlist + admin token |

## 3. Rate Limit 설계

외부 금융사 retry는 정상 동작일 수 있지만, 짧은 시간에 과도하게 몰리면 DB와 Redis에 부담을 준다. Rate limit은 요청을 무조건 막기 위한 장치가 아니라, 시스템을 보호하면서 idempotency가 동작할 시간을 벌기 위한 장치다.

```nginx
limit_req_zone $binary_remote_addr zone=event_api:10m rate=20r/s;

location /api/v1/transaction-events {
    limit_req zone=event_api burst=50 nodelay;
    proxy_pass http://api_backend;
}
```

rate limit이 발생하면 운영자는 Nginx log, API idempotency metric, Redis lock rejected metric을 함께 봐야 한다. 단순히 429만 증가했다고 장애로 볼 수는 없다. 외부 시스템 retry storm을 정상적으로 완화한 결과일 수 있기 때문이다.

## 4. Nginx log에 남겨야 할 것

장애 대응에서는 Nginx와 API 로그를 연결해야 한다. 그래서 Nginx access log에는 `trace_id`, `request_id`, `upstream_response_time`, `status`, `request_time`을 남기는 것이 중요하다.

반대로 HMAC signature, raw request body, account number 원문은 남기지 않는다. 추적 가능성과 민감정보 보호는 함께 설계해야 한다.

## 5. 트레이드오프

Nginx에서 접근 제어를 강화하면 API 서버의 부담은 줄어든다. 하지만 정책이 Nginx와 API에 흩어지면 운영자가 어느 계층에서 차단됐는지 헷갈릴 수 있다. 따라서 Nginx는 네트워크/경로/속도 제한을 담당하고, API는 HMAC, request validation, idempotency 같은 application-level 정책을 담당하도록 역할을 분리한다.

## 6. 완료 기준

```bash
make nginx-test
make rate-limit-test
make admin-access-test
```

Nginx config test, rate limit 동작, internal endpoint 접근 제한이 모두 재현되어야 한다.
