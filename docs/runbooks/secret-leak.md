# Secret Leak Runbook

## 1. 장애 정의

HMAC secret, client secret, API token, GitHub Actions secret, backup encryption key가 노출되었거나 노출이 의심되는 상태다.

Secret leak은 이벤트 위조와 관리자 접근 우회로 이어질 수 있으므로 SEV1으로 분류한다.

## 2. 사용자 영향

- 외부인이 거래 이벤트를 위조할 가능성
- 관리자 endpoint 접근 가능성
- 백업 파일 복호화 가능성
- CI/CD credential 오남용 가능성

## 3. 즉시 확인할 Dashboard

- Security dashboard: auth failure, unknown client, replay failure
- API dashboard: unusual request rate
- GitHub Actions: secret scan result

## 4. Alert Rule

```yaml
annotations:
  runbook: "docs/runbooks/secret-leak.md"
```

확인할 alert:

- `SecretScanFailed`
- `HmacAuthFailureSpike`
- `UnknownClientSpike`

## 5. 1차 확인 명령

```bash
make security-log-check
make secret-scan
git log --all --decorate --oneline
```

## 6. 원인 분기표

| 관측 결과 | 판단 | 대응 |
|---|---|---|
| Git에 secret commit | repository leak | 즉시 rotation, history 대응 검토 |
| CI log에 secret 출력 | pipeline leak | log masking, secret 재발급 |
| HMAC 실패 급증 | brute force 또는 잘못된 secret | partner/client 확인 |
| backup key 노출 | backup leak 위험 | backup key rotation |

## 7. 대응 절차

1. 노출된 secret 범위를 식별한다.
2. 해당 secret을 즉시 revoke 또는 rotate한다.
3. previous/current secret 동시 허용 기간을 최소화한다.
4. 관련 partner/client에 변경 절차를 안내한다.
5. auth failure와 forged request 여부를 확인한다.
6. secret scan과 HMAC smoke test를 재실행한다.

## 8. 복구 확인 기준

- 노출 secret 폐기 완료
- current secret으로 정상 요청 성공
- previous secret으로 요청 실패
- secret scan 통과
- CI log에 secret 미출력

## 9. 재발 방지

- pre-commit secret scan 검토
- GitHub Actions secret masking 점검
- rotation 절차 문서화
- secret_version 로그만 허용

## 10. 사후 기록 템플릿

- 발견 시간:
- secret 유형:
- 노출 범위:
- rotation 완료 시간:
- 영향 요청:
- 재발 방지:
