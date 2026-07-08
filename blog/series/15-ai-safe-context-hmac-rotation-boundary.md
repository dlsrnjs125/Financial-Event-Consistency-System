# AI 요약과 HMAC Rotation을 붙이기 전에 먼저 막아야 했던 것들

운영 자동화를 붙일수록 보안 경계가 중요해진다. 장애 분석에 AI를 쓰거나 partner secret rotation을 자동화하려면, 먼저 무엇을 절대 넘기면 안 되는지 정해야 한다.

## AI-safe context는 allowlist로 만들었다

incident, recovery, reconciliation evidence에는 raw account, retry key, authorization, signature, request body가 섞일 수 있다. 이 값을 AI context에 넣으면 분석이 아니라 유출이다.

그래서 PH6는 allowlist 기반 sanitizer를 사용했다.

```text
input:  account_no, authorization, hmac_signature, raw_request_body, account_token
output: account_token
summary: $.account_no removed, $.authorization removed, $.hmac_signature removed, $.raw_request_body removed
```

중요한 점은 redaction summary에도 제거된 raw value를 남기지 않는 것이다.

## HMAC next secret은 dry-run에서만 허용했다

Secret rotation에서도 비슷한 경계가 있었다. `current`, `previous`, `next`, `revoked`, `disabled`를 구분하지 않으면 rollout 준비와 production 승인 경계가 섞인다.

`next` secret 검증이 성공했다는 것은 rollout 준비가 됐다는 뜻이지, 실제 write API에서 사용할 수 있다는 뜻이 아니다. 그래서 `allow_next_for_dry_run=true`는 drill/demo verifier 경로로만 제한했다.

## 자동화보다 먼저 필요한 것

AI는 복구 실행자가 아니고, next secret은 production write 권한이 아니다. 운영 자동화는 편의보다 먼저 데이터와 권한 경계를 설명할 수 있어야 한다.
