# Secret Rotation은 단순히 key를 바꾸는 일이 아니었다

금융 이벤트 API에서 HMAC은 외부 partner 요청이 위조되지 않았다는 최소한의 계약이다. 그런데 운영에서 더 어려운 문제는 서명 검증 자체보다 secret을 바꾸는 과정이다.

PH7의 질문은 이것이었다.

```text
Secret rotation 중 어떤 key를 언제까지 허용할 것인가?
```

## 하나의 static secret으로 설명할 수 없는 상황

secret이 하나뿐이면 rotation 중 partner 배포 순서에 따라 정상 요청이 실패할 수 있다. 반대로 old/new secret을 무기한 둘 다 허용하면 rotation이 아니라 permanent dual-secret 상태가 된다.

그래서 PH7에서는 Vault/KMS를 붙이기 전에 version 기반 HMAC 검증 계약을 먼저 고정했다.

## current, previous, next, revoked, disabled를 나눈 이유

PH7 verifier는 secret state를 다음처럼 나눈다.

| 상태 | 의미 | 처리 |
| --- | --- | --- |
| current | 현재 활성 secret | 허용 |
| previous | 직전 secret | rotation window 안에서만 허용 |
| next | 배포 전 staged secret | drill dry-run에서만 허용 |
| revoked | 폐기된 secret | 거부 |
| disabled | 비활성 client/key | 거부 |

핵심은 `previous`와 `next`를 다르게 보는 것이다. `previous`는 짧은 호환 window를 위한 것이고, `next`는 아직 실제 write API에서 활성화되면 안 되는 staged secret이다.

## next를 실제 write API에서 막은 이유

처음에는 next secret dry-run이 성공하면 실제 API에서도 허용해도 되는지 고민했다. 하지만 그것은 rollout 준비와 production 승인 경계를 섞는 일이다.

그래서 실제 write API에서는 `next`를 허용하지 않는다. `allow_next_for_dry_run=true`는 PH7 drill/demo verifier 경로에서만 사용한다.

## signature와 canonical request를 evidence에 남기지 않은 이유

보안 기능을 검증하려고 만든 evidence가 다시 유출 경로가 되면 안 된다. PH7 report에는 raw secret, raw signature, raw request body, Authorization header를 남기지 않는다.

대신 report에는 tokenized client, key id, secret status, decision reason, body hash, canonical request hash, signature presence 같은 안전한 evidence만 남긴다.

## 구현 중 실제로 잡은 문제

세 가지를 특히 조심했다.

- provided signature를 report에 남기지 않기
- previous secret을 무기한 허용하지 않기
- next secret을 실제 write API에서 승인 전 허용하지 않기

이 중 next secret 문제는 dry-run과 write API의 차이를 테스트로 고정했다. rotation 준비가 곧 production 활성화를 뜻하지 않게 만든 것이다.

## 검증한 것

PH7은 다음 명령과 test로 검증한다.

```bash
make ph7-hmac-rotation-demo
make ph7-hmac-rotation-validate
make ph7-hmac-rotation-smoke
make ph7-security-check
```

report validator는 raw secret/signature/body 후보를 검사하고, API dependency test는 next secret이 실제 write API에서 거부되는지 확인한다.

## Rotation contract까지만 고정했다

PH7에서 고정한 것은 current/previous/next/revoked/disabled secret 상태와 sanitized rotation evidence를 통한 HMAC rotation contract다.

Vault/KMS 연동, 실제 partner key retirement, persistent nonce store, production rotation approval workflow는 아직 남아 있다. 이 경계를 분리해야 dry-run 성공이 곧 production 활성화라는 오해를 막을 수 있다.
