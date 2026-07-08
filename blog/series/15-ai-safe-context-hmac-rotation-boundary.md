# AI 요약과 HMAC Rotation을 붙이기 전에 먼저 막아야 했던 것들

AI에게 incident context를 넘기기 전에 먼저 해야 할 일은 프롬프트를 잘 쓰는 것이 아니었다. 어떤 데이터가 절대 넘어가면 안 되는지 정하고, redaction 결과 자체가 민감정보를 다시 노출하지 않게 만드는 일이 먼저였다.

HMAC rotation도 마찬가지다. next secret을 미리 검증할 수는 있어야 하지만, 실제 write API에서 next secret이 accepted되면 rollout 전 권한이 열린다.

## AI-safe context의 기준

PH6 sanitizer는 denylist만 믿지 않는다. allowlist를 먼저 평가하고, 허용된 field만 AI context로 보낸다.

허용 후보는 다음처럼 제한했다.

- classification
- severity
- count summary
- masked identifier
- tokenized identifier
- hash value
- run id
- report path

raw account number, raw idempotency key, Authorization header, HMAC signature, raw request body는 금지한다.

## redaction summary에도 raw value를 남기지 않은 이유

처음에는 "무엇을 지웠는지" 보여주기 위해 redaction summary에 일부 값을 남길 수 있다고 생각했다.

하지만 summary가 다음처럼 되면 sanitizer가 새로운 유출 경로가 된다.

```json
{
  "removed": "$.authorization",
  "value": "Bearer raw-token"
}
```

그래서 summary에는 path, reason, type만 남기고 raw value는 남기지 않는다.

```json
{
  "path": "$.authorization",
  "reason": "sensitive_key_removed",
  "value_included": false
}
```

## HMAC secret 상태를 나눈 이유

Partner secret rotation은 단순히 key를 하나 더 추가하는 일이 아니다. 상태별로 write API 허용 여부를 분리해야 한다.

| 상태 | write API 허용 | dry-run 허용 | 의미 |
| --- | --- | --- | --- |
| current | O | O | 현재 production 검증 기준 |
| previous | O 또는 제한적 허용 | O | rotation 직후 grace period |
| next | X | O | rollout 준비 검증 |
| revoked | X | X | 폐기 |
| disabled | X | X | 비활성 |

`next` secret은 dry-run에서는 검증할 수 있어야 한다. 그래야 partner가 전환 전에 signature 계산이 맞는지 확인할 수 있다.

하지만 실제 write API에서 `next`가 accepted되면 아직 배포되지 않은 secret이 production 권한을 갖게 된다.

## 트러블슈팅: dry-run 성공과 write 성공은 다르다

초기 구현에서는 signature verification helper가 current/previous/next 후보를 같은 방식으로 볼 위험이 있었다.

그래서 실제 write API와 dry-run endpoint의 허용 secret set을 분리했다.

```text
write API
  -> current, previous only

dry-run
  -> current, previous, next
```

dry-run은 readiness check다. 복구 실행 권한이나 금융 write 권한이 아니다.

## 남은 한계

이 단계는 Vault/KMS 기반 secret delivery나 partner별 staged rollout workflow를 완성하지 않는다. 또한 AI가 recovery action을 자동으로 선택하거나 실행하지 않는다.

목표는 AI와 rotation을 붙이기 전에, 어떤 context와 secret state가 어느 경계 안에서만 허용되는지 명확히 하는 것이다.
