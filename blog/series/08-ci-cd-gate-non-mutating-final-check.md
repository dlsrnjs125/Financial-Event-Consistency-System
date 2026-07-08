# 배포 Gate는 코드를 고치는 명령이 아니라 실패를 알려주는 명령이어야 했다

CI/CD Gate는 배포 전에 문제를 알려줘야 한다. 그런데 검증 명령이 파일을 수정한다면, "검증"과 "자동 수정"이 섞인다.

이 글은 `final-check`를 non-mutating gate로 정리한 이유와, format/lint/test/security 검증을 어떻게 분리했는지 정리한다.

## 문제 상황

처음에는 local check나 final check에 format 명령을 넣고 싶었다. 개발자가 한 번만 실행하면 코드가 고쳐지고 테스트까지 돌면 편하기 때문이다.

하지만 배포 Gate의 의미는 다르다.

```text
검증 전 working tree A
final-check 실행
format이 파일을 수정
테스트는 수정 후 working tree B를 검증
```

이러면 CI가 어떤 상태를 검증했는지 애매해진다.

## 설계 판단

고치는 명령과 검증하는 명령을 분리했다.

```text
make format
make fix
  -> 파일을 수정할 수 있음

make final-check
make format-check
make lint
make test
  -> 파일을 수정하면 안 됨
```

`final-check`는 배포 직전 문지기다. 문지기는 코드를 고치는 역할이 아니라, 지금 상태가 통과 가능한지 알려주는 역할이다.

## final-check 구성

대표적인 검증 흐름은 다음과 같다.

```text
format-check
lint
compile
unit tests
consistency tests
security-log-check
secret scan
```

format check는 `black --check`, `isort --check-only`처럼 동작해야 한다. 실제 format 적용은 별도 명령에서만 한다.

## 보안 검증도 역할을 나눴다

`security-log-check`는 structured log field에 raw sensitive 값이 들어가지 않는지 확인한다.

secret scan은 repository에 secret이 들어가지 않았는지 본다.

둘 다 필요하지만 같은 검사가 아니다.

| 검사 | 목적 |
| --- | --- |
| security-log-check | 로그 설계가 raw account/idempotency/signature를 남기지 않는지 |
| secret scan | repository에 credential이 들어가지 않았는지 |
| sanitizer validation | AI context/report에 민감정보가 남지 않는지 |

## 트러블슈팅: CI 실패는 빨리 알려야 한다

format이 깨졌을 때 CI가 자동으로 고쳐주면 developer는 실패를 놓칠 수 있다. 특히 deployment gate에서는 "고쳐진 결과"가 아니라 "현재 commit이 통과 가능한지"가 중요하다.

그래서 format 문제는 실패로 보고, developer가 local에서 `make format`을 실행한 뒤 다시 commit하도록 했다.

## evidence

로컬에서는 다음처럼 확인한다.

```bash
make format-check
make test
make security-log-check
make final-check
```

문서만 바꾼 경우에도 `git diff --check`, Markdown link check, hidden Unicode check를 함께 돌려서 리뷰 품질 문제를 줄인다.

## 남은 한계

CI Gate는 운영 장애를 모두 막지 못한다. Redis down, PostgreSQL down, latency spike 같은 drill은 별도 evidence runner와 runbook으로 분리해야 한다.

그래도 non-mutating gate 원칙은 중요하다. 배포 Gate는 코드를 대신 고치는 도구가 아니라, 배포하면 안 되는 상태를 빠르게 알려주는 마지막 문이다.
