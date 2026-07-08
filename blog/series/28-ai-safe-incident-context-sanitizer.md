# 장애 분석에 AI를 쓰기 전에 먼저 한 일

장애 분석에 AI를 쓰면 보고서 초안이나 원인 후보 정리에 도움이 될 수 있다. 하지만 금융 운영 evidence를 그대로 AI context에 넣으면 분석 도구가 아니라 정보 유출 경로가 된다.

PH6의 질문은 이것이었다.

```text
AI를 장애 분석에 쓰기 전에 어떤 데이터를 제거해야 하는가?
```

## AI 요약보다 먼저 필요한 것은 context 정리였다

PH2~PH5를 거치며 incident, recovery case, reconciliation report가 생겼다. 이 evidence에는 운영 판단에 필요한 요약도 있지만, 원문 요청이나 인증 자료처럼 절대 외부 분석 context에 들어가면 안 되는 데이터도 섞일 수 있다.

그래서 PH6에서는 AI 호출을 만들지 않았다. 먼저 AI-safe context를 만드는 sanitizer를 구현했다.

## Denylist만으로는 부족했다

처음에는 민감 key를 denylist로 막으면 충분해 보였다. 하지만 artifact schema는 계속 변할 수 있고, 새 필드가 추가될 때 denylist가 따라가지 못할 수 있다.

또 `token`이라는 문자열을 전부 막으면 `account_token`, `event_token` 같은 가명 식별자까지 사라진다. access token과 pseudonymous token은 다르게 다뤄야 했다.

## Allowlist 기반 sanitizer를 선택한 이유

PH6는 allowlist를 먼저 평가한다. 운영자 추적에 필요한 bounded field, masked field, hash/token field만 남기고 나머지는 제거한다.

허용 예시는 다음 범주다.

- masked identifier
- pseudonymous token
- hash evidence
- consistency count
- severity/classification/status
- bounded route, phase, result label

반대로 plain financial identifier, retry identifier, request body, auth material, signing material, secret은 제거한다.

## Redaction summary도 유출 경로가 될 수 있다

redaction summary는 무엇을 지웠는지 설명해야 한다. 하지만 지운 값을 그대로 summary에 남기면 sanitizer가 다시 유출 경로가 된다.

그래서 PH6 summary에는 field path와 reason만 남기고 raw value는 남기지 않는다.

## recovery case까지 포함한 이유

PH6는 incident artifact만 대상으로 끝나지 않는다. recovery case evidence와 reconciliation report도 AI-safe context 후보가 될 수 있다.

그래서 `sanitize-latest --source recovery-cases` 경로를 추가하고, `masked_target_id` 같은 운영 추적용 masked field도 allowlist에 포함했다. 복구 후보를 설명할 수는 있어야 하지만, 원문 식별자를 넘기면 안 된다.

## 검증한 것

테스트는 allowlisted field 유지, unknown field 제거, nested 민감 필드 제거, redaction summary raw value 미포함, token/hash 보존, recovery case latest source 처리, generated context validation을 확인한다.

sample artifact에도 account/retry/signature 성격의 제거 evidence를 남겨 sanitizer가 무엇을 막는지 보이게 했다.

## 이 글에서 말할 수 있는 것과 말하면 안 되는 것

말할 수 있는 것은 PH6가 incident/recovery/reconciliation evidence를 AI-safe context로 축약하고, 민감 데이터를 allowlist 기반으로 제거한다는 점이다.

말하면 안 되는 것은 PH6가 외부 AI API를 호출하거나, AI가 복구안을 자동 채택하거나, sanitized context가 복구 실행 권한을 의미한다는 주장이다.
