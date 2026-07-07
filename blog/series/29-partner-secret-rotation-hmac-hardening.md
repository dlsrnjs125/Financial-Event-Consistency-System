# 29. Partner Secret Rotation과 HMAC Hardening

금융 이벤트 API에서 HMAC은 외부 partner 요청이 위조되지 않았다는 최소한의 계약이다.
하지만 운영에서 더 어려운 지점은 "secret을 어떻게 바꿀 것인가"다.

secret이 하나뿐이면 rotation 중 partner 배포 순서에 따라 정상 재시도 요청이 실패할 수 있다.
반대로 old/new secret을 무기한 둘 다 허용하면 rotation이 아니라 permanent dual-secret 상태가 된다.

PH7에서는 실제 Vault나 KMS를 붙이기 전에, version 기반 HMAC 검증 정책을 코드와 drill evidence로 먼저 고정했다.

## 구현한 것

요청 헤더는 partner rotation mode에서 다음 값을 요구한다.

```text
X-Client-Id
X-Key-Id
X-Timestamp
X-Nonce
X-Signature
```

canonical request는 아래 형식으로 만들었다.

```text
{method}
{path}
{timestamp}
{nonce}
{body_sha256}
```

여기서 raw body는 report나 log에 남기지 않고, 검증에는 `body_sha256`만 사용한다.
signature 비교는 `hmac.compare_digest`로 수행해 일반 문자열 비교보다 안전하게 처리했다.

## Rotation 상태

PH7 verifier는 secret version 상태를 다음처럼 나눈다.

| 상태 | 의미 | 처리 |
| --- | --- | --- |
| current | 현재 활성 secret | 허용 |
| previous | 직전 secret | rotation window 안에서만 허용 |
| next | 배포 전 staged secret | dry-run에서만 허용 |
| revoked | 폐기된 secret | 거부 |
| disabled | 비활성 client/key | 거부 |

핵심은 `previous`를 영구 허용하지 않는 것이다.
`previous_valid_until`이 지나면 `previous_expired`로 거부한다.

## Evidence를 남길 때 더 조심한 것

보안 기능을 검증하려고 만든 report가 또 다른 유출 경로가 되면 의미가 없다.

그래서 PH7 report에는 다음만 남긴다.

- `client_token`
- `key_id`
- `secret_status`
- `decision_reason`
- `body_hash`
- `canonical_request_hash`
- `signature_present`
- `raw_secret_included=false`
- `raw_signature_included=false`
- `raw_body_included=false`

raw secret, raw signature, Authorization header, raw request body는 report에 남기지 않는다.

## Drill 명령

```bash
make ph7-hmac-rotation-demo
make ph7-hmac-rotation-validate
make ph7-hmac-rotation-smoke
make ph7-security-check
```

sample report는 아래 위치에 생성된다.

```text
reports/security/ph7-hmac-rotation/sample-hmac-rotation-report.json
reports/security/ph7-hmac-rotation/sample-hmac-rotation-report.md
```

## 트러블슈팅 기록

### raw signature를 evidence에 넣으면 안 되는 문제

- 문제: invalid signature를 설명하려다 provided signature를 report에 남길 수 있었다.
- 원인: 보안 검증 evidence와 운영 디버깅 로그의 경계를 분리하지 않으면 raw 인증 자료가 섞인다.
- 해결: report에는 `signature_present`와 hash evidence만 남겼다.
- 검증: `ph7_hmac_rotation_drill.py validate`에서 raw secret/signature/body 후보를 검사한다.

### previous secret을 무기한 허용하면 안 되는 문제

- 문제: old secret이 계속 허용되면 rotation 완료 기준이 없다.
- 원인: dual-secret window에 종료 시점을 두지 않으면 폐기 검증이 불가능하다.
- 해결: `previous_valid_until` 이후 `previous_expired`로 거부한다.
- 검증: unit test와 sample report에 expired previous case를 고정했다.

### next secret을 기본 허용하면 안 되는 문제

- 문제: staged secret이 승인 전에 활성화될 수 있다.
- 원인: rollout 준비용 secret과 실서비스 current secret을 구분하지 않으면 조기 활성화된다.
- 해결: `allow_next_for_dry_run=true`일 때만 `next_dry_run`으로 허용했다.
- 검증: dry-run flag가 없으면 거부하고, 있을 때만 성공하는 테스트를 추가했다.

## 남긴 한계

PH7은 secret rotation의 운영 계약을 검증하는 단계다.

아직 하지 않은 것:

- Vault/KMS/Secret Manager 연동
- 실제 partner secret 교체 승인 workflow
- persistent nonce store
- production key retirement 자동화

이 경계가 중요하다.
자동화는 검증과 evidence 생성까지 담당하고, 실제 금융 책임이 생기는 key retirement와 partner 공지는 사람이 승인한다.
