# 배포 Gate는 코드를 고치는 명령이 아니라 실패를 알려주는 명령이어야 했다

CI/CD Gate는 배포 전에 문제를 알려줘야 한다. 그런데 검증 명령이 파일을 수정한다면, "검증"과 "자동 수정"이 섞인다.

## final-check가 working tree를 바꾸면 안 된다

처음에는 final check에 format 명령을 넣고 싶었다. 하지만 format은 파일을 고친다. 개발자가 검증을 실행했는데 working tree가 바뀌면, 어떤 상태를 검증한 것인지 애매해진다.

그래서 `final-check`는 non-mutating 명령으로 구성했다.

```text
format-check
lint
compile
test
security-log-check
```

고치는 명령은 `make fix`나 `make format`으로 분리했다.

## 보안 검증도 역할을 나눴다

`security-log-check`는 structured log field에 raw sensitive 값이 들어가지 않는지 확인한다. secret scan은 repository에 secret이 들어가지 않았는지 본다.

둘 다 필요하지만 같은 검사가 아니다. 하나는 로그 설계 검증이고, 다른 하나는 repository 유출 방지다.

## Gate의 의미

배포 Gate는 코드를 대신 고쳐주는 도구가 아니다. 배포하면 안 되는 상태를 빠르게 알려주는 도구다. 이 경계를 분리해야 CI가 신뢰할 수 있는 마지막 문이 된다.
