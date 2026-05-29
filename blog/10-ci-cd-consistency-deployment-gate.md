# 10편. CI/CD에서 정합성 테스트를 배포 Gate로 사용하는 방법

## 들어가며

개발자들은 코드를 작성할 때 의도하지 않게 정합성을 깨는 코드를 만들 수 있습니다.

이 편에서는 **CI/CD에서 정합성 테스트를 배포 Gate**로 설정하여 이를 방지합니다.

---

## CI 파이프라인

Phase 11에서는 이미 있던 GitHub Actions workflow를 새로 만드는 대신, 배포 전 정합성 Gate로 고도화했다. 핵심 job은 다음처럼 정리했다.

| Gate | Job | 막으려는 문제 |
|---|---|---|
| Format/Lint | `lint` | 스타일 오류와 정적 오류 |
| Unit Test | `unit-tests` | 도메인 로직 회귀 |
| Consistency Test | `consistency-tests` | 중복 반영, idempotency conflict, 상태 전이 오류 |
| Migration Test | `migration-tests` | PostgreSQL migration 실패와 제약 누락 |
| Security Log Check | `security-log-check` | raw 민감 필드 구조화 로그 노출 |
| Secret Scan | `secret-scan` | repository credential 유출 |
| Docker Build | `docker-build` | 배포 이미지 생성 실패 |
| Gate Summary | `gate-check` | 필수 Gate 결과 종합 |

여기서 중요한 점은 CI가 모든 운영 시나리오를 재현하는 장소가 아니라는 점이다. PR Gate는 빠르게 실패를 알려줘야 한다. 그래서 중복 반영 방지, idempotency replay, migration, 보안 로그 검사처럼 빠르고 회귀 위험이 큰 검증은 CI에 넣고, k6 peak/duplicate storm 같은 무거운 테스트는 수동 또는 릴리즈 전 검증으로 분리했다.

---

## 로컬 Gate와 CI Gate를 맞춘 이유

CI에서만 돌아가는 검증은 실패했을 때 디버깅이 느리다. 그래서 로컬에서도 비슷한 순서로 확인할 수 있도록 Makefile 명령을 맞췄다.

```bash
make ci-local
make final-check
make security-log-check
```

`final-check`는 특히 의미를 명확히 했다. 처음에는 최종 확인 명령에 `format`이 포함되어 있어 실행하면 black/isort가 파일을 수정할 수 있었다. 하지만 최종 검증 명령은 working tree를 바꾸지 않고 성공/실패만 판단해야 한다. 그래서 `final-check`는 `format-check`, `lint`, `compile`, `test`, `security-log-check`처럼 non-mutating 검증으로 정리했다.

자동 수정은 별도 명령으로 남겨야 한다. 그래야 "검증을 통과했다"와 "검증 중 파일이 수정됐다"가 섞이지 않는다.

## CI Gate를 만들면서 발견한 문제

첫 번째는 `final-check`가 코드를 수정하는 문제였다. 최종 검증 명령은 깨끗한 working tree에서 성공/실패만 판단해야 한다. 그런데 format 명령이 포함되어 있으면 검증 과정에서 파일이 바뀐다. 그래서 `final-check`는 `format-check`, `lint`, `compile`, `test`, `security-log-check`처럼 non-mutating 명령으로 구성했다.

두 번째는 security scan의 역할 혼동이었다. `security-log-check`는 repository secret 유출을 찾는 도구가 아니다. 이 명령은 운영 코드 경로에서 `idempotency_key=`, `account_no=`, `signature=`, `secret=`, `raw_body=` 같은 raw structured logging 패턴을 막는다. 반대로 TruffleHog는 repository에 실제 credential이 들어갔는지 확인한다. 두 검사는 서로 대체할 수 없다.

세 번째는 외부 GitHub Action을 floating ref로 사용하는 문제였다. 처음에는 secret scan action을 `trufflesecurity/trufflehog@main`으로 두었다. 동작은 했지만, 보안 Gate가 외부 action의 main 브랜치를 따라가면 어느 시점에 CI 결과가 달라질 수 있다. 그래서 재현성을 위해 version tag로 고정했다. 이 프로젝트에서는 TruffleHog action ref를 고정해 어느 날 갑자기 스캔 동작이 바뀌는 위험을 줄였다.

마지막으로 k6 heavy test를 PR 필수 Gate에 넣지 않았다. duplicate storm과 Redis Down 테스트는 중요하지만 PR마다 실행하면 피드백이 느려진다. 대신 빠른 consistency regression은 CI에 넣고, heavy performance는 수동/릴리즈 전 Gate로 분리했다.

## migration smoke test를 넣은 이유

정합성 시스템에서 테스트 코드가 통과해도 migration이 깨지면 배포는 실패한다. 특히 이 프로젝트는 `transaction_events.external_event_id`, `idempotency_records.idempotency_key`, `ledger_entries.transaction_event_id` 같은 unique constraint가 마지막 방어선이다. migration이 이 제약을 만들지 못하면 애플리케이션 로직이 아무리 좋아도 DB 레벨 중복 방어가 사라진다.

그래서 migration Gate는 SQLite가 아니라 PostgreSQL service container에서 실행하도록 했다. `alembic upgrade head` 이후 현재 revision과 핵심 constraint 존재 여부를 확인한다. 이 검증은 "테이블이 만들어졌다"보다 더 구체적이다. 배포 후 정합성에 직접 영향을 주는 제약이 살아 있는지를 확인하기 때문이다.

## 검증 결과와 남은 한계

Phase 11 정리 후 로컬에서는 다음 명령으로 빠른 Gate를 재현할 수 있다.

```bash
make ci-local
make final-check
make security-log-check
```

GitHub Actions에서는 `lint`, `unit-tests`, `consistency-tests`, `migration-tests`, `security-log-check`, `secret-scan`, `docker-build`가 실행되고, `gate-check`가 전체 결과를 종합한다. 하나라도 실패하면 main 병합 전에 원인을 확인할 수 있다.

남은 한계도 있다. TruffleHog는 PR Gate 안정성을 위해 verified secret 중심으로 사용한다. 오탐은 줄어들지만 unverified secret-like pattern까지 강하게 잡는 정책은 별도 보강이 필요하다. 또한 k6 heavy test는 CI 필수 Gate가 아니므로, Redis Down duplicate storm이나 peak load 검증은 릴리즈 전 수동 명령으로 확인해야 한다.
