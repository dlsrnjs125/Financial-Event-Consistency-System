# Redis 장애는 버티고, PostgreSQL 장애는 막는다

장애 재현을 Docker Compose로 만들면서 가장 크게 배운 점은 코드 설계와 인프라 설정이 서로 모순될 수 있다는 점이었다.

## Redis를 hard dependency로 걸면 fallback을 검증할 수 없다

처음에는 `depends_on`에서 Redis health를 강하게 걸었다. 그런데 이 프로젝트에서 Redis는 degraded dependency다. Redis가 내려가도 PostgreSQL 기준 정합성을 유지하며 처리해야 한다.

문제는 Compose 설정이었다.

```text
Redis unhealthy
-> API container가 시작되지 않음
-> 코드에 fallback이 있어도 실제 환경에서 검증 불가
```

그래서 PostgreSQL은 hard dependency로 두고, Redis는 API 시작을 막지 않게 조정했다. 대신 `/ready`와 metric에서 Redis degraded 상태를 노출한다.

## PostgreSQL down은 다른 문제다

PostgreSQL은 최종 Source of Truth다. PostgreSQL write path가 불가능하면 신규 금융 write를 성공으로 처리할 근거가 없다.

따라서 Redis 장애는 degraded mode로 버티지만, PostgreSQL write 장애는 fail-closed로 막는다. 이 차이를 Compose와 readiness 정책에도 반영해야 했다.

## 장애 재현의 목적

Docker Compose drill은 운영 환경을 완전히 대체하지 않는다. 하지만 dependency policy가 코드, readiness, metric, runbook에서 같은 말을 하는지 확인하는 데 충분히 유용했다.
