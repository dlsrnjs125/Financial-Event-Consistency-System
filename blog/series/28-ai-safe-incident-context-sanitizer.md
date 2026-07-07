# 장애 분석에 AI를 쓰기 전에, 왜 Sanitized Context가 먼저 필요했나

## 1. 문제

장애 분석 자동화나 AI 요약은 운영자의 판단 속도를 높일 수 있다.
하지만 금융 운영 evidence에는 raw request body, raw idempotency key, account number, Authorization header, HMAC signature 같은 값이 섞일 수 있다.

이 값을 그대로 AI context에 넣으면 분석 도구가 아니라 정보 유출 경로가 된다.

## 2. 처음에 의심한 방식

처음에는 단순 masking이나 denylist로 충분한지 검토했다.
하지만 새 필드가 artifact에 추가되면 denylist가 따라가지 못할 수 있다.
또 `token`이 들어간 모든 필드를 막으면 `account_token` 같은 안전한 가명 식별자까지 사라진다.

## 3. 선택한 방식

PH6에서는 allowlist 기반 sanitizer를 선택했다.

- Level 2~3 데이터 중심으로 context를 구성한다.
- `account_token`, `event_token`, `idempotency_key_hash`, `request_hash`는 명시적으로 허용한다.
- raw account number, raw idempotency key, request body, signature, Authorization, secret은 제거한다.
- redaction summary에는 raw value가 아니라 field path와 reason만 남긴다.

## 4. 구현 중 트러블슈팅

nested dict/list 내부의 민감 필드가 빠지지 않도록 재귀 처리를 추가했다.
또 redaction summary 자체가 유출 경로가 되지 않도록 제거된 값은 저장하지 않았다.

`token` 문자열을 전부 금지하는 방식은 `account_token`까지 제거하는 문제가 있어 allowlist 우선 정책으로 풀었다.
runtime artifact는 `reports/ai-context/run-*/`로 분리하고, repository에는 curated sample만 남기도록 했다.

## 5. 검증

검증은 다음 기준으로 잡았다.

- unit test로 allowlist 유지와 forbidden field 제거 확인
- nested dict/list 민감 필드 제거 확인
- raw value가 redaction summary에 남지 않는지 확인
- CLI demo와 validate로 sample artifact 검증
- security-log-check 기준 유지

## 6. 결론

PH6에서 AI는 복구 실행자가 아니다.
AI는 sanitized evidence를 바탕으로 운영자의 분석과 report 초안을 돕는 assistant로 제한된다.

금전 상태 변경, write resume, 보정 SQL, 고객 영향 판단은 계속 사람의 승인 영역으로 남긴다.
