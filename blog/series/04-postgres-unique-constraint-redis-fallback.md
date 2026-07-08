# Redis Lock을 믿지 않고 PostgreSQL Unique Constraint를 마지막 방어선으로 둔 이유

Redis lock은 중복 요청을 앞에서 줄여주는 좋은 도구다. 하지만 금융 이벤트 정합성의 최종 기준이 될 수는 없다. Redis는 성능 최적화 계층이고, PostgreSQL은 최종 Source of Truth다.

## Redis Lock은 왜 필요했나

동일 이벤트 요청 100개가 동시에 들어오면, Redis lock은 DB에 들어오는 요청 수를 줄여준다. 정상 상황에서는 불필요한 DB transaction을 줄이고 응답 흐름을 안정시킨다.

하지만 Redis lock을 획득했다는 사실은 원장 반영의 근거가 아니다. lock은 메모리 상태이고, 장애나 재시작으로 사라질 수 있다.

## Redis가 죽으면 정합성도 깨지는가

깨지면 안 된다. Redis가 내려가면 lock/cache 없이 DB fallback으로 처리한다. 이때 모든 요청이 PostgreSQL까지 들어올 수 있지만, `transaction_events.external_event_id`와 `ledger_entries.transaction_event_id` unique constraint가 마지막 방어선이 된다.

```text
Redis up: lock이 중복 요청을 앞에서 완화
Redis down: 요청이 DB까지 도달
PostgreSQL unique constraint: 중복 원장 반영 차단
```

## transaction boundary를 기준으로 묶었다

이벤트 생성, ledger 생성, account balance 변경, idempotency completion은 하나의 DB transaction 안에서 설명되어야 한다. repository가 commit하지 않고 service가 transaction boundary를 관리하는 이유도 여기에 있다.

결론은 단순하다. Redis는 빠른 중복 완화 장치이고, PostgreSQL unique constraint는 마지막 정합성 방어선이다. 둘의 역할을 섞지 않는 것이 장애 상황에서 더 안전했다.
