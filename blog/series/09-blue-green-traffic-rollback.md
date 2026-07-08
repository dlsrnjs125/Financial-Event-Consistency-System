# 배포 실패 시 DB를 되돌리지 않고 트래픽만 Blue로 되돌린 이유

금융 이벤트 시스템에서 rollback은 조심스럽다. API 컨테이너를 이전 버전으로 되돌리는 것과, 이미 반영된 금융 데이터를 되돌리는 것은 전혀 다른 문제다.

이 프로젝트의 Blue-Green 배포는 DB rollback이 아니라 traffic rollback을 목표로 했다. schema 변경은 backward-compatible migration으로 관리하고, 장애가 발생하면 Nginx upstream을 Blue로 되돌린다.

## 문제 상황

CI Gate를 통과한 코드라도 운영 트래픽에 바로 노출하면 위험하다. 특히 거래 이벤트 처리 시스템에서는 새 버전이 잘못된 상태 전이를 만들거나 idempotency 판단을 깨뜨리면 중복 원장 반영으로 이어질 수 있다.

그래서 배포 절차를 다음처럼 정의했다.

1. 기존 Blue는 계속 트래픽을 받는다.
2. Green을 별도로 띄운다.
3. Green의 `/health`, `/ready`, smoke test를 먼저 검증한다.
4. Nginx 설정을 검증한 뒤 upstream만 Green으로 바꾼다.
5. 전환 후 Nginx 경유 smoke와 정합성 검증을 다시 실행한다.
6. 문제가 생기면 DB가 아니라 API traffic만 Blue로 되돌린다.

## 구현 구조

Docker Compose에는 `api-blue`, `api-green`, `nginx`가 있다.

```text
external request
  -> localhost:8080
  -> nginx
  -> api-blue:8000 또는 api-green:8000
```

Green은 사람이 직접 확인하기 위해 host `8001`로 노출하지만, 컨테이너 내부에서는 Blue와 동일하게 `8000`으로 listen한다.

```text
host -> localhost:8001 -> api-green container:8000
nginx container -> http://api-green:8000
```

Nginx는 전체 설정 파일을 매번 수정하지 않는다. active upstream snippet만 교체한다.

```text
infra/nginx/conf.d/upstream-active.conf
infra/nginx/conf.d/upstream-active.conf.blue
infra/nginx/conf.d/upstream-active.conf.green
```

전환은 다음 명령으로 재현한다.

```bash
make ops2-start-blue
make ops2-check-blue
make ops2-start-green
make ops2-check-green
make ops2-smoke-green
make ops2-switch-green
make ops2-check-routed-green
make ops2-smoke-routed
make ops2-rollback
make ops2-demo-full
```

## routed identity를 evidence로 남긴 이유

`/health`가 200이라고 해서 Green으로 전환됐다는 뜻은 아니다. Blue도 200이고 Green도 200일 수 있다.

그래서 API `/health` 응답에 배포 identity를 넣었다.

```json
{
  "status": "ok",
  "deployment_color": "green",
  "instance_id": "api-green"
}
```

초기 상태에서는 Nginx가 Blue upstream을 바라보고 있고, 실제 `/health` 응답도 `deployment_color=blue`, `instance_id=api-blue`로 확인된다.

![Blue routed identity](../images/ops-phase-2/01-blue-routed-identity.png)

Green 전환 후에는 설정 파일만 확인하지 않고, Nginx 경유 응답이 실제 `api-green`에서 왔는지 확인한다.

![Green switch routed identity](../images/ops-phase-2/02-green-switch-routed-identity.png)

Rollback 후에는 active upstream과 실제 response identity가 다시 Blue로 복구됐는지 확인한다.

![Rollback blue routed identity](../images/ops-phase-2/03-rollback-blue-routed-identity.png)

마지막으로 Blue 시작, Green 검증, traffic switch, routed smoke, Blue rollback, PostgreSQL 정합성 검증까지 통합 evidence로 남긴다.

![Ops2 demo full consistency gate](../images/ops-phase-2/04-ops2-demo-full-consistency-gate.png)

## 트러블슈팅 1: 설정은 Green인데 실제 트래픽은 Blue일 수 있다

처음에는 active upstream file과 `nginx -T` 출력만 확인했다. 하지만 이것은 "설정상 Green"일 뿐, 실제 HTTP 응답이 Green에서 왔다는 증거는 아니었다.

그래서 `ops2-check-routed-green`은 다음을 함께 확인하도록 바꿨다.

- `.active-color`가 `green`인지
- active upstream snippet이 `api-green:8000`을 포함하는지
- Nginx에 로드된 config가 `api-green:8000`을 포함하는지
- Nginx 경유 `/health` 응답의 `deployment_color`가 `green`인지
- Nginx 경유 `/health` 응답의 `instance_id`가 `api-green`인지

설정 검증과 실제 응답 검증을 분리한 것이 핵심이었다.

## 트러블슈팅 2: host port와 container port를 혼동했다

host에서는 Green을 `localhost:8001`로 확인한다. 하지만 Nginx는 Docker network 내부에서 `api-green:8000`으로 접근해야 한다.

처음 이 차이를 놓치면 Green 직접 호출은 성공하지만, Nginx 전환 후 upstream 연결은 실패할 수 있다.

최종 Nginx upstream은 다음처럼 잡았다.

```nginx
upstream api_backend {
    server api-green:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}
```

그리고 Nginx 컨테이너 내부에서 Green health를 직접 확인하는 검증을 추가했다.

```bash
docker compose exec -T nginx wget -qO- http://api-green:8000/health
```

## 트러블슈팅 3: reload 실패 시 상태 drift

가장 위험했던 지점은 Nginx reload 실패였다.

파일은 Green으로 바뀌고 `.active-color`도 Green으로 기록됐는데 reload가 실패하면, 실제 Nginx process는 여전히 Blue로 트래픽을 보낼 수 있다. 이 상태에서는 표시 상태와 실제 트래픽 상태가 어긋난다.

그래서 upstream 전환 순서를 다음처럼 바꿨다.

1. 현재 active snippet을 backup으로 저장한다.
2. target snippet을 candidate로 만든다.
3. candidate를 active file로 교체한다.
4. `nginx -t`를 실행한다.
5. Nginx reload를 실행한다.
6. 실패 시 backup snippet과 active color를 이전 값으로 복구한다.

전환과 rollback은 같은 공통 함수로 처리한다. 사고 가능성이 큰 로직을 여러 스크립트에 흩어놓지 않기 위해서다.

## 트러블슈팅 4: Green 시작 명령이 Blue를 건드리면 안 된다

처음에는 `ops2-start-green`이 내부적으로 `ops2-start-blue`를 먼저 실행하도록 구성했다. Blue가 떠 있어야 Green 배포를 확인할 수 있다는 이유였다.

하지만 이 구조는 Green만 검증하려던 명령이 Blue/Nginx/PostgreSQL/Redis 상태까지 다시 건드릴 수 있다.

그래서 명령을 분리했다.

- `ops2-start-blue`: Blue/Nginx/PostgreSQL/Redis를 명시적으로 시작한다.
- `ops2-start-green`: Blue/Nginx가 실행 중인지 확인한다. 없으면 실패한다.
- `ops2-deploy-green-only`: Green만 실행하고 검증한다.

운영 리허설 명령은 의도하지 않은 재시작을 만들면 안 된다.

## Redis degraded는 배포 차단 사유가 아니다

Redis는 최종 Source of Truth가 아니므로 degraded 상태에서도 PostgreSQL 기준 정합성이 유지될 수 있다. 따라서 Redis degraded는 배포 중 경고이지만, PostgreSQL이 healthy이고 smoke/consistency gate가 통과한다면 Green 검증 자체를 막는 hard dependency로 두지 않았다.

반대로 PostgreSQL이 down이면 신규 write를 성공 처리할 수 없으므로 배포 smoke도 통과할 수 없다.

## 남은 한계

Docker Compose 기반 Blue-Green은 운영 Kubernetes rollout과 같지 않다. progressive traffic shifting, autoscaling, service mesh retry는 별도 환경에서 다뤄야 한다.

그래도 이 시뮬레이션은 Green 검증, Nginx 전환, reload 실패 복구, rollback 후 정합성 검증이라는 핵심 절차를 로컬에서 반복 실행할 수 있게 만든다.
