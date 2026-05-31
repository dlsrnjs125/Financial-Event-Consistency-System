# Secret Management Policy

> 이 문서는 Ops Phase 7 Internal Network Security를 보완하기 위한 supporting document입니다.
> 별도의 추가 Ops Phase가 아닙니다.

## 1. 목적

HMAC secret과 client secret은 금융 이벤트 위조 방지의 핵심이다.

Secret 관리는 생성, 저장, 주입, 회전, 폐기 절차까지 포함해야 한다.

## 2. 기본 정책

- `.env`는 로컬 개발 전용이다.
- `.env.example`에는 키 이름과 더미 값만 제공한다.
- 실제 secret은 Git에 커밋하지 않는다.
- GitHub Actions secret은 로그에 출력하지 않는다.
- secret 값은 structured log, trace, metric label에 넣지 않는다.
- secret 변경 후 재배포와 smoke 검증 절차를 정의한다.

## 3. HMAC Secret Rotation

외부 제휴사별 secret은 회전 가능해야 한다.

Rotation 정책:

1. partner/client id별 `active_secret_version`을 둔다.
2. rotation 기간에는 previous/current secret을 모두 허용한다.
3. 검증 로그에는 `secret_version`만 남기고 secret 원문은 남기지 않는다.
4. rotation 완료 후 previous secret은 폐기한다.
5. rotation 완료 후 HMAC smoke test를 실행한다.

## 4. Secret 주입 방식

| 환경 | 주입 방식 |
|---|---|
| Local | `.env` |
| CI | GitHub Actions Secret |
| Docker Compose | env file 또는 environment variable |
| 운영 후보 | Secret Manager 또는 Ansible Vault |

## 5. 검증 명령어

```bash
make security-log-check
make secret-scan
make hmac-smoke
```

성공 기준:

- Git repository에 실제 secret 없음
- CI log에 secret 출력 없음
- HMAC 요청 정상 처리
- previous/current secret 동시 허용 기간 동작 확인
- rotation 완료 후 previous secret 거부 확인

## 6. 사고 대응

Secret 유출이 의심되면 [Secret Leak Runbook](runbooks/secret-leak.md)을 따른다.
