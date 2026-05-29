# 9편. Docker Compose 기반 장애 재현 환경 만들기

## 들어가며

지금까지 설계하고 구현하고 테스트했습니다.

이제 **실제 장애를 재현**해야 합니다.

이 편에서는 Docker Compose로 Redis, PostgreSQL, API, Nginx, Prometheus, Grafana를 한 번에 띄우고 장애를 시뮬레이션합니다.

---

## Docker Compose 구성

Docker Compose 환경은 PostgreSQL, Redis, API, Nginx, Prometheus, Grafana를 함께 띄운다. 여기서 중요한 점은 단순히 컨테이너를 많이 띄우는 것이 아니라, 장애를 일부러 만들고 다시 복구할 수 있어야 한다는 점이다.

Phase 10 이후 Compose 의존성 정책도 바뀌었다. PostgreSQL은 정합성의 최종 기준이므로 hard dependency다. 반대로 Redis는 lock/cache 최적화 계층이므로 degraded dependency다. Redis가 unhealthy라고 해서 API 컨테이너가 시작 자체를 못 하면 "Redis 장애 시 DB 기준 fallback"이라는 설계와 충돌한다. 그래서 API의 Redis 의존성은 서비스 시작 여부 정도로만 두고, 실제 장애 판단은 `/ready` body와 metric에서 확인하도록 정리했다.

---

## 장애 재현 시나리오

### 시나리오 1: Redis 다운
```bash
make local-bg
make failure-redis-down
make k6-redis-down-duplicate-storm
make k6-verify
make failure-redis-up
```

이 시나리오의 목적은 Redis가 내려간 상황에서도 PostgreSQL unique constraint, DB transaction, idempotency record가 마지막 방어선으로 동작하는지 확인하는 것이다. Redis Down duplicate storm에서 중요한 성공 기준은 p95가 낮은지가 아니라 중복 Ledger 반영이 0건인지다.

### 시나리오 2: PostgreSQL 연결 풀 고갈
```bash
make failure-db-down
curl -i http://localhost:8000/ready
make failure-db-up
```

PostgreSQL 장애는 Redis 장애와 다르게 처리한다. PostgreSQL은 source of truth이므로 연결할 수 없다면 정합성을 보장할 수 없다. 이 경우 `/ready`는 실패해야 하고, API가 정상 트래픽 대상으로 남아 있으면 안 된다.

### 시나리오 3: API 서버 재시작
```bash
make failure-api-restart
make failure-status
make k6-verify
```

---

## 장애 명령을 따로 만든 이유

장애 재현은 문서에 "Redis를 내려본다"라고 쓰는 것만으로는 부족했다. 매번 다른 방식으로 컨테이너를 내리면 어떤 상태에서 테스트했는지 재현하기 어렵다. 그래서 Makefile에 장애 주입 명령을 고정했다.

```bash
make failure-redis-down
make failure-redis-up
make failure-db-down
make failure-db-up
make failure-api-restart
make failure-status
```

이 명령들은 의도적으로 destructive action을 포함하지 않는다. 특히 DB volume 삭제나 전체 `docker compose down -v` 같은 명령은 만들지 않았다. 장애 재현의 목적은 데이터를 없애는 것이 아니라, 기존 데이터와 정합성 조건이 유지되는 상태에서 dependency failure를 관찰하는 것이다.

## 개발 중 발견한 충돌

가장 큰 충돌은 Redis degraded 정책과 Compose dependency 설정이었다. 코드와 문서에서는 Redis를 degraded dependency로 정의했지만, Compose에서 Redis health를 hard dependency로 두면 Redis가 unhealthy한 순간 API 컨테이너 자체가 시작되지 않는다. 그러면 fallback 로직이 아무리 있어도 실제 실행 환경에서는 검증할 수 없다.

이 문제는 "애플리케이션 readiness 정책"과 "오케스트레이션 dependency 정책"이 같은 메시지를 가져야 한다는 점을 보여줬다. PostgreSQL은 hard dependency, Redis는 degraded dependency로 분리했고, Redis 상태는 `/ready` body와 metric에 남기되 API 인스턴스를 바로 죽은 것으로 보지 않도록 했다.

두 번째 충돌은 장애 명령의 복구 경로였다. `failure-db-down`만 있고 `failure-db-up`이 없으면 장애 재현 후 개발자가 수동으로 상태를 복구해야 한다. 장애 주입 명령은 down/up/status가 세트로 있어야 반복 가능하다. 그래서 Redis와 DB 모두 복구 명령을 제공했다.

## 검증 기준

장애 재현 명령을 만든 뒤에는 각 장애마다 성공 기준을 다르게 봤다.

| 시나리오 | 성공 기준 |
|---|---|
| Redis Down | `/ready` degraded, PostgreSQL 기준 중복 반영 0건 |
| Redis Timeout | fallback log/metric 기록, DB 처리 가능 요청 유지 |
| PostgreSQL Down | `/ready` 실패, 정합성 보장 불가 상태를 명확히 노출 |
| API Restart | 재시작 후 idempotency replay와 duplicate prevention 유지 |
| Duplicate Storm | 동일 key 요청이 여러 번 들어와도 Ledger 반영 1회 |

Docker Compose는 운영 orchestrator가 아니다. multi-node 장애, network partition, autoscaling, 실제 load balancer health check까지 완전히 재현하지는 못한다. 그래도 로컬에서 같은 장애를 같은 명령으로 반복할 수 있게 만든 것은 이후 Phase 10 fallback, Phase 12 Blue-Green 검증의 기반이 됐다.
