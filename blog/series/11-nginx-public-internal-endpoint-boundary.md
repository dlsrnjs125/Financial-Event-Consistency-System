# /metrics와 /ready를 public API에서 숨긴 이유

운영 endpoint는 편하지만 위험하다. `/metrics`, `/ready`, `/docs`, `/openapi.json`은 내부 상태와 장애 정보를 노출할 수 있다. 외부 금융사 호출 경로와 운영자 접근 경로는 같으면 안 된다.

## public endpoint를 줄였다

public Nginx에서 허용할 것은 최소화했다.

- `GET /health`
- `POST /api/v1/transaction-events`

반대로 다음은 public에서 차단했다.

- `/metrics`
- `/ready`
- `/docs`
- `/openapi.json`
- `/admin/*`

## 운영 endpoint 접근 제어 모델

운영자나 Prometheus가 보는 endpoint는 내부 network, allowlist, token 같은 별도 통제가 필요하다.

```text
External Partner -> Public Nginx -> transaction API
Operator/Monitoring -> Internal path -> ready/metrics/admin
```

## 로그도 endpoint만큼 중요했다

운영 로그에 raw account number, idempotency key, HMAC signature, client secret, request body가 남으면 endpoint를 막아도 유출 경로가 생긴다.

그래서 public/internal endpoint 분리와 함께 masking, signature 저장 금지, security-log-check를 같이 둔다. 운영 편의와 정보 노출 사이의 균형을 명시적으로 잡은 것이다.
