# Redis 장애는 버티고, PostgreSQL 장애는 막는다

장애 재현은 "컨테이너를 꺼본다"가 아니다. 어떤 dependency가 죽었을 때 API가 계속 받아도 되는지, 어떤 dependency가 죽으면 즉시 막아야 하는지를 정책으로 고정하는 일이다.

이 프로젝트에서는 Redis와 PostgreSQL의 의미가 다르다.

- Redis는 lock/cache/fallback 대상인 보조 계층이다.
- PostgreSQL은 최종 Source of Truth다.

따라서 Redis down은 degraded로 버티고, PostgreSQL write path down은 fail-closed로 막는다.

## Redis를 hard dependency로 두면 오히려 설계가 깨졌다

처음에는 Docker Compose `depends_on`과 application readiness를 비슷하게 생각했다. Redis가 unhealthy면 API 컨테이너도 시작하지 않는 편이 안전해 보였다.

하지만 이 판단은 시스템 정책과 충돌했다. Redis는 성능 최적화 계층이므로 죽어도 PostgreSQL transaction과 unique constraint로 최종 정합성을 유지해야 한다.

Redis가 내려갔다고 API 컨테이너 시작 자체를 막으면 "Redis degraded에서도 DB 기준으로 처리한다"는 설계가 Compose 단계에서 깨진다.

## dependency 정책

최종 정책은 다음처럼 나눴다.

| Dependency | 역할 | Compose policy | Readiness policy | API write 의미 |
| --- | --- | --- | --- | --- |
| PostgreSQL | Source of Truth | hard dependency | unhealthy면 not ready | 신규 금융 write 차단 |
| Redis | lock/cache optimization | service started | degraded로 노출 | DB fallback 가능 |
| API | transaction boundary | restart 가능 | health/ready 분리 | DB 기준 일관성 |

PostgreSQL은 최종 commit evidence가 남는 곳이므로 hard dependency다. Redis는 없어도 DB transaction을 통해 중복 방어가 가능해야 하므로 degraded dependency다.

## 장애 명령을 따로 만든 이유

장애 재현은 문서에 "Redis를 내려본다"라고 쓰는 것만으로는 부족했다. 매번 다른 방식으로 컨테이너를 내리면 어떤 상태에서 검증했는지 재현하기 어렵다.

그래서 Makefile 명령으로 고정했다.

```bash
make failure-redis-down
make k6-redis-down-duplicate-storm
make k6-verify
make failure-redis-up
```

PostgreSQL과 API 재시작도 별도 명령으로 분리했다.

```bash
make failure-postgres-down
make failure-postgres-up
make failure-api-restart
```

이 명령들은 장애를 "데이터 삭제"가 아니라 "dependency 상태 변화"로 다룬다.

## DB volume 삭제는 장애 재현이 아니라 데이터 파괴다

반대로 다음 명령은 장애 drill entrypoint로 만들지 않았다.

```bash
docker compose down -v
```

DB volume 삭제는 dependency failure가 아니라 데이터 파괴다. 장애 재현의 목적은 기존 데이터가 유지된 상태에서 Redis down, PostgreSQL down, API restart를 관찰하는 것이다.

PostgreSQL restore나 volume 재생성은 DR drill에서 따로 다뤄야 한다.

## 트러블슈팅: Compose policy와 readiness policy가 충돌했다

처음에는 Redis를 `service_healthy`로 걸었다.

```yaml
depends_on:
  redis:
    condition: service_healthy
```

이렇게 하면 Redis가 down일 때 API가 시작하지 못한다. 그런데 애플리케이션 정책은 Redis down을 degraded로 보고 PostgreSQL fallback을 허용한다.

그래서 Compose 조건을 `service_started`로 낮추고, 실제 dependency 상태는 `/ready`와 metric에서 판단하도록 바꿨다.

```yaml
depends_on:
  postgres:
    condition: service_healthy
  redis:
    condition: service_started
```

## evidence를 어떻게 남겼나

Redis Down duplicate storm에서는 p99와 error rate가 나빠졌지만 ledger 중복은 0건이었다. 이것은 Redis 장애가 성능/가용성에는 영향을 주지만, PostgreSQL 방어선이 중복 반영을 막았다는 evidence다.

PostgreSQL down에서는 신규 금융 write를 성공으로 처리하지 않는다. `/ready` 실패와 `503 + Retry-After`를 통해 외부 시스템이 같은 idempotency key로 나중에 재시도할 수 있게 한다.

## 남은 한계

Docker Compose는 운영 orchestrator가 아니다. Kubernetes readiness probe, restart policy, service mesh retry, managed Redis/PostgreSQL failover와는 차이가 있다.

하지만 Compose drill은 dependency policy를 코드, readiness, Makefile, runbook에서 같은 말로 유지하는 데 충분한 회귀 검증 역할을 한다.
