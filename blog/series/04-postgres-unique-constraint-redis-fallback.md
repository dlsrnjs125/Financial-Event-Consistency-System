# Redis Lock을 믿지 않고 PostgreSQL Unique Constraint를 마지막 방어선으로 둔 이유

Redis lock은 중복 요청을 앞에서 줄여주는 좋은 도구다. 하지만 금융 이벤트 정합성의 최종 기준이 될 수는 없다.

Redis는 성능 최적화 계층이고, PostgreSQL은 최종 Source of Truth다.

## Redis가 막지 못한 요청은 어디서 마지막으로 막아야 할까?

동일 이벤트 요청 100개가 동시에 들어오면 모든 요청이 DB transaction까지 도달할 수 있다. Redis lock은 이 압력을 줄여준다.

하지만 Redis lock을 획득했다는 사실은 원장 반영의 근거가 아니다. lock은 메모리 상태이고, 장애나 재시작으로 사라질 수 있다.

## Redis Lock이 정답처럼 보였던 이유

처음에는 Redis lock만 잘 잡으면 중복 요청 대부분을 막을 수 있다고 생각했다.

하지만 장애 시나리오를 넣으면 질문이 바뀐다.

```text
Redis가 down이면?
lock TTL이 너무 짧으면?
lock은 잡았지만 DB commit 전에 API가 죽으면?
```

이 질문에 답하려면 Redis가 아니라 PostgreSQL을 마지막 방어선으로 둬야 했다.

## 왜 Redis 고가용성이나 Redlock을 핵심으로 두지 않았나

실제 운영에서는 Redis Sentinel, Redis Cluster, managed Redis, timeout tuning, circuit breaker를 함께 고려해야 한다. Redis 자체의 가용성을 높이는 것은 중요하다.

하지만 이 프로젝트에서 Redis HA를 먼저 풀지 않은 이유는 명확하다. Redis를 아무리 안정화해도 금융 원장의 최종 정합성 기준이 Redis가 되면 안 되기 때문이다.

Redis lock은 같은 Idempotency-Key 요청이 동시에 DB transaction에 진입하는 수를 줄이고, 완료 응답 cache로 DB 조회를 줄이며, duplicate storm 중 DB 부하를 완화할 수 있다.

하지만 Redis lock이 있다고 해서 원장이 한 번만 반영되었다는 증거가 생기는 것은 아니다. lock TTL이 만료될 수 있고, API가 lock 획득 후 DB commit 전에 죽을 수 있으며, Redis 장애 중에는 lock 자체가 없다.

그래서 이번 프로젝트에서는 Redis HA보다 먼저 "Redis가 없어도 PostgreSQL 기준 정합성이 유지되는가"를 검증했다. Redis의 고가용성은 성능과 가용성 개선 과제이고, PostgreSQL unique constraint는 정합성 방어선이다.

## Redis가 내려가도 남아 있어야 하는 제약조건

PostgreSQL에는 다음 unique constraint가 필요하다.

```text
transaction_events.external_event_id unique
ledger_entries.transaction_event_id unique
idempotency_records.idempotency_key unique
```

Redis가 살아 있으면 lock이 중복 요청을 앞에서 완화한다.

Redis가 죽으면 요청이 DB까지 더 많이 도달한다.

그래도 PostgreSQL unique constraint가 중복 event와 duplicate ledger를 막아야 한다.

```text
Redis up
  -> lock/cache로 중복 요청 완화

Redis down
  -> DB fallback
  -> PostgreSQL unique constraint로 최종 방어
```

## event, ledger, balance, idempotency를 같은 transaction에 둔 이유

이벤트 생성, ledger 생성, account balance 변경, idempotency completion은 하나의 DB transaction 안에서 설명되어야 한다.

repository가 commit하지 않고 service가 transaction boundary를 관리하는 이유도 여기에 있다.

```text
begin transaction
  insert transaction_event
  insert ledger_entry
  update account balance
  complete idempotency record
commit
```

중간에 실패하면 전체가 rollback되어야 한다.

## Lock 획득 실패는 거래 실패가 아니다

Redis lock을 얻지 못했다는 것은 반드시 장애가 아니다. 같은 Idempotency-Key 요청이 이미 처리 중이라는 신호일 수 있다.

그래서 lock rejected를 `500`으로 보지 않고, 처리 중 재요청으로 해석해 `202 Accepted`를 반환하는 정책을 선택했다. 완료 응답 replay는 lock이 풀린 뒤 DB IdempotencyRecord 또는 cache 경로에서 확인한다.

이 선택은 일부 구간에서 즉시 완료 응답을 주지 못하고 `202`를 반환할 수 있다는 trade-off가 있다. 대신 중복 DB transaction 진입을 줄이고, 처리 중인 같은 요청을 신규 거래로 오해하지 않게 만든다.

## 트러블슈팅: Redis failure를 consistency failure로 만들지 않기

Redis가 죽었을 때 API latency와 error rate가 나빠질 수 있다. 하지만 그 자체가 ledger 중복을 의미하지는 않는다.

Redis Down duplicate storm에서 p99는 3490ms까지 상승했고 error rate도 6.86%가 나왔다. 하지만 ledger 중복은 0건이었다.

이 결과는 Redis 장애 중 가용성 개선이 필요하다는 뜻이지, PostgreSQL 방어선이 실패했다는 뜻은 아니다.

## evidence

검증 명령은 Redis 정상과 Redis down을 분리한다.

```bash
make k6-duplicate
make k6-verify

make failure-redis-down
make k6-redis-down-duplicate-storm
make k6-verify
make failure-redis-up
```

`make k6-verify`는 HTTP 성공률이 아니라 DB 중복 row와 ledger 중복을 확인한다.

## 남은 한계

Redis fallback은 최종 정합성을 지키기 위한 설계이지, 좋은 latency를 보장하는 설계가 아니다.

운영 수준의 안정성을 위해서는 Redis timeout tuning, circuit breaker, connection pool metric, backpressure policy가 추가로 필요하다.

결론은 단순하다. Redis는 빠른 중복 완화 장치이고, PostgreSQL unique constraint는 마지막 정합성 방어선이다.
