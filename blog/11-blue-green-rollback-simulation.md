# 11편. Blue-Green 배포와 Rollback 시뮬레이션

## 1. 문제를 어떻게 정의했는가

CI Gate를 통과한 코드라도 바로 운영 트래픽에 노출하면 위험하다. 금융 이벤트 처리 시스템에서는 배포 중에도 같은 이벤트가 두 번 반영되면 안 되고, 잘못된 상태 전이가 새 버전에서 발생하면 즉시 이전 버전으로 되돌릴 수 있어야 한다.

그래서 Phase 12에서는 배포를 "컨테이너를 새로 띄우는 일"이 아니라 다음 절차로 정의했다.

1. 기존 Blue는 계속 트래픽을 받는다.
2. Green을 별도로 띄운다.
3. Green의 `/health`, `/ready`, smoke test를 먼저 검증한다.
4. Nginx 설정을 검증한 뒤 upstream만 Green으로 바꾼다.
5. 전환 후 다시 smoke와 정합성 검증을 실행한다.
6. 문제가 생기면 DB를 되돌리는 것이 아니라 API traffic만 Blue로 되돌린다.

## 2. 처음 세운 가설

처음에는 Nginx upstream을 Blue에서 Green으로 바꾸고 reload하면 충분하다고 생각했다.

```text
api-blue:8000  -> api-green:8000
nginx -s reload
```

하지만 실제 배포 스크립트를 만들면서 전환보다 중요한 것은 실패했을 때의 복구라는 점이 드러났다. Green이 준비되지 않았거나, Nginx config test는 통과했지만 reload가 실패하거나, host port와 container port를 혼동하면 전환은 성공한 것처럼 보이지만 실제 트래픽은 실패할 수 있다.

## 3. 구현한 구조

Docker Compose에는 `api-blue`, `api-green`, `nginx`가 있다.

```text
외부 요청
  -> localhost:8080
  -> nginx
  -> api-blue:8000 또는 api-green:8000
```

Green은 사람이 직접 확인하기 위해 host `8001`로 노출하지만, 컨테이너 내부에서는 Blue와 동일하게 `8000`으로 listen한다.

```text
host -> localhost:8001 -> api-green container:8000
nginx container -> http://api-green:8000
```

Nginx는 `nginx.conf` 전체를 sed로 수정하지 않는다. 대신 active upstream snippet만 교체한다.

```text
infra/nginx/conf.d/upstream-active.conf
infra/nginx/conf.d/upstream-active.conf.blue
infra/nginx/conf.d/upstream-active.conf.green
```

## 4. 어떻게 재현했는가

배포 흐름은 Makefile 명령으로 고정했다.

```bash
make local-bg
make deploy-status
make deploy-green
make deploy-switch-green
make deploy-smoke
make deploy-rollback
make deploy-verify
```

전체 전환과 rollback 흐름은 한 번에 실행할 수 있다.

```bash
make phase12-check
```

이 명령은 Green 실행, Green smoke, Nginx Green 전환, 전환 후 smoke, Blue rollback, rollback 후 smoke, PostgreSQL 정합성 검증까지 실행한다.

## 5. 트러블슈팅 1: reload 실패 시 상태 drift

가장 위험했던 지점은 Nginx reload 실패였다.

예를 들어 파일은 Green으로 바뀌었고 `.active-color`도 Green으로 기록됐는데, 실제 `nginx -s reload`가 실패하면 Nginx process는 여전히 Blue로 트래픽을 보낼 수 있다. 이 상태에서는 상태 파일은 Green이라고 말하지만 실제 트래픽은 Blue로 가는 drift가 생긴다.

그래서 upstream 전환은 다음 순서로 바꿨다.

1. 현재 active snippet을 backup으로 저장한다.
2. target snippet을 candidate로 만든다.
3. candidate를 active file로 교체한다.
4. `nginx -t`를 실행한다.
5. `nginx -s reload`를 실행한다.
6. reload 실패 시 backup snippet과 active color를 이전 값으로 복구한다.

이렇게 하면 reload 실패가 발생해도 "표시 상태"와 "실제 트래픽 상태"가 어긋나는 상황을 줄일 수 있다.

## 6. 트러블슈팅 2: host port와 container port 혼동

처음 Green을 검증할 때 host에서는 `localhost:8001`로 접근한다. 이 때문에 Nginx upstream도 `api-green:8001`로 쓰기 쉽다.

하지만 Nginx는 같은 Docker network 안에서 Green 컨테이너에 접근한다. Docker network 내부에서는 host port가 아니라 container port를 써야 한다.

최종 구조는 다음처럼 정리했다.

```yaml
api-green:
  environment:
    API_PORT: 8000
  ports:
    - "8001:8000"
```

Nginx upstream은 다음과 같다.

```nginx
upstream api_backend {
    server api-green:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}
```

이 문제는 host에서 `localhost:8001/health`가 성공해도 Nginx가 Green에 붙지 못할 수 있다는 점 때문에 중요했다. 그래서 배포 스크립트에 Nginx 컨테이너 내부에서 Green health를 직접 확인하는 검증을 넣었다.

```bash
docker compose exec -T nginx wget -qO- http://api-green:8000/health
```

## 7. 트러블슈팅 3: Redis degraded는 배포 차단 사유가 아니다

Phase 10에서 Redis는 degraded dependency로 정의했다. PostgreSQL이 살아 있으면 Redis lock/cache가 실패해도 DB transaction과 unique constraint 기준으로 처리할 수 있다.

그런데 Docker Compose에서 Redis를 `service_healthy` hard dependency로 두면 Redis가 unhealthy일 때 Green 컨테이너 자체가 시작되지 않는다. 이는 readiness 정책과 orchestration 정책이 충돌하는 구조다.

그래서 API 컨테이너 dependency를 다음처럼 정리했다.

```yaml
depends_on:
  postgres:
    condition: service_healthy
  redis:
    condition: service_started
```

PostgreSQL은 Source of Truth이므로 hard dependency다. Redis는 최적화 계층이므로 컨테이너 시작을 막지 않고, 애플리케이션 `/ready`에서 `mode="degraded"`로 노출한다.

## 8. 검증 결과

`make phase12-check` 실행 결과 Green 전환과 Blue rollback 흐름이 통과했다.

확인한 항목은 다음과 같다.

| 검증 항목 | 결과 |
|---|---|
| Green `/health` | 200 OK |
| Green `/ready` | 200 OK |
| Nginx internal `api-green:8000/health` | 200 OK |
| Nginx Green 전환 후 smoke | 통과 |
| Blue rollback 후 smoke | 통과 |
| duplicated ledger event count | 0 |
| duplicated external event count | 0 |

배포 smoke는 단순 health check가 아니라 HMAC 거래 이벤트 생성, 동일 Idempotency-Key replay, validation failure를 함께 확인한다. 따라서 Green이 "떠 있다"가 아니라 "핵심 거래 API를 처리할 수 있다"를 검증한다.

## 9. 포기한 것

DB rollback은 자동화하지 않았다. 금융 데이터 schema rollback은 데이터 손실 위험이 크기 때문이다. Phase 12의 rollback은 API traffic rollback이다. schema 변경은 backward-compatible migration 원칙으로 관리한다.

또한 k6 peak나 duplicate storm을 기본 배포 단계에 넣지 않았다. 배포 기본 단계는 빠른 smoke와 readiness 검증으로 유지하고, heavy test는 수동 또는 릴리즈 전 Gate로 분리했다.

## 10. 남은 한계

Docker Compose 기반 Blue-Green은 운영 Kubernetes rollout과 같지 않다. service discovery, progressive traffic shifting, readiness probe, autoscaling은 별도 환경에서 다뤄야 한다.

그래도 이 시뮬레이션은 배포 전 Green 검증, Nginx 전환, reload 실패 복구, rollback 후 정합성 검증이라는 핵심 절차를 로컬에서 반복 실행할 수 있게 만든다.
