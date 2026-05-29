# Phase 12 - Blue-Green Deployment & Rollback Simulation

## 1. 목적

Phase 12는 Phase 11 CI Gate를 통과한 변경을 실제 트래픽에 노출하기 전 Green 환경에서 검증하고, Nginx upstream 전환과 rollback을 Docker Compose로 재현하는 단계다.

금융 이벤트 시스템에서는 배포 중에도 동일 이벤트 중복 반영, 잘못된 상태 전이, idempotency replay 실패가 발생하면 안 된다. 따라서 배포 절차는 단순 컨테이너 교체가 아니라 "배포 전 검증 -> 트래픽 전환 -> 이상 감지 -> rollback -> 정합성 검증" 흐름으로 관리한다.

## 2. 현재 구조

| 구성요소 | 역할 |
|---|---|
| `api-blue` | 현재 운영 트래픽을 받는 안정 API |
| `api-green` | 신규 배포 후보 API, `green-deployment` profile로 실행 |
| `nginx` | `upstream-active.conf`를 통해 Blue 또는 Green으로 트래픽 전달 |
| PostgreSQL | Blue/Green이 공유하는 최종 정합성 저장소 |
| Redis | Blue/Green이 공유하는 lock/cache 계층 |
| Prometheus/Grafana | API 도메인 metric과 dashboard 확인 |

Docker Compose에서도 이 dependency 정책을 맞춘다.
`api-blue`와 `api-green`은 PostgreSQL을 `service_healthy` hard dependency로 기다리지만, Redis는 `service_started`만 요구한다.
따라서 Redis가 unhealthy여도 컨테이너 시작 자체가 막히지 않고, 애플리케이션 `/ready`가 `mode="degraded"`로 상태를 노출한다.

Nginx upstream은 `infra/nginx/conf.d/upstream-active.conf`만 교체한다.
Blue template은 `api-blue:8000`, Green template은 `api-green:8000`을 사용한다.
Green의 host port는 `8001:8000`으로 매핑해 사람이 `http://localhost:8001`로 직접 검증할 수 있게 하고, 컨테이너 내부 listen port는 Blue와 동일한 8000으로 유지한다.

## 3. 배포 흐름

| 순서 | 단계 | 명령/검증 |
|---:|---|---|
| 1 | CI Gate 통과 | Phase 11 GitHub Actions |
| 2 | Green 컨테이너 실행 | `make deploy-green` |
| 3 | Green health/readiness 확인 | `GREEN_URL/health`, `GREEN_URL/ready` |
| 4 | Green smoke test | `scripts/deployment-smoke.sh` |
| 5 | migration-smoke 확인 | `make migration-smoke`로 적용된 schema/constraint 검증 |
| 6 | consistency 검증 | lightweight smoke와 `make deploy-verify` |
| 7 | Nginx upstream Green 전환 | `make deploy-switch-green` |
| 8 | 전환 후 smoke | `make deploy-smoke` |
| 9 | metric 관찰 | Prometheus/Grafana, `make deploy-status` |
| 10 | 이상 시 rollback | `make deploy-rollback` |

전체 흐름:

```bash
make local-bg
make deploy-blue-green
make deploy-verify
```

## 4. Rollback 흐름

Rollback 조건:

- Green readiness 실패
- Green smoke test 실패
- Nginx config test 실패
- 전환 후 `/health` 또는 `/ready` 실패
- 전환 후 5xx 증가
- 잘못된 상태 전이 또는 reconciliation failure 발생

Rollback 명령:

```bash
ROLLBACK_REASON="post-switch smoke failed" make deploy-rollback
```

Rollback 후 검증:

- Nginx `/health` 200
- Nginx `/ready` 200
- `make deploy-smoke` 성공
- `make deploy-verify`에서 중복 Ledger/Event 0건

DB rollback은 자동 수행하지 않는다.
이 프로젝트의 rollback은 API traffic rollback이며, schema 변경은 backward-compatible migration 원칙으로 관리한다.

## 5. 명령어

| 명령 | 목적 |
|---|---|
| `make deploy-status` | active upstream, Blue/Green/Nginx 상태, 확인 URL 출력 |
| `make deploy-green` | Green 컨테이너 실행과 Green health/readiness/smoke 확인 |
| `make deploy-switch-green` | Green health/readiness를 재확인하고 Nginx upstream을 Green으로 전환 |
| `make deploy-blue-green` | Green 검증, upstream 전환, 전환 후 smoke 실행 |
| `make deploy-rollback` | Nginx upstream을 Blue로 되돌리고 smoke 확인 |
| `make deploy-smoke` | Nginx 기준 lightweight smoke test 실행 |
| `make deploy-verify` | PostgreSQL 정합성 검증 SQL 실행 |
| `make phase12-check` | Green 전환, rollback, smoke, 정합성 검증 전체 흐름 |
| `make phase12-rollback-check` | Green 전환 후 Blue rollback 검증 |

## 6. 검증 기준

| 항목 | 기준 | 검증 방법 |
|---|---|---|
| Green health | 200 OK | `curl /health` |
| Green readiness | 200 OK | `curl /ready` |
| Redis degraded | 허용 | `/ready mode`와 `checks.redis` 확인 |
| PostgreSQL failed | 차단 | `/ready` 실패 |
| Smoke test | 성공 | `make deploy-smoke` |
| Idempotency | 동일 key 재요청 동일 결과 | deployment smoke |
| State transition | 잘못된 전이 차단 | consistency/unit test |
| Nginx config | `nginx -t` 성공 | switch 전 확인 |
| Rollback | Blue 전환 성공 | rollback 후 `/ready` |
| 정합성 | 중복 Ledger/Event 0건 | `make deploy-verify` 또는 SQL |

## 7. 배포 전후 관측 지표

- `financial_http_errors_total`
- `financial_http_request_duration_seconds` p95/p99
- `financial_invalid_state_transition_total`
- `financial_reconciliation_failures_total`
- `financial_redis_fallback_total`
- `financial_readiness_dependency_status`
- Nginx upstream 상태: `make deploy-status`
- Container 상태: `docker compose ps`

현재 Prometheus scrape는 FastAPI API metric 중심이다.
Nginx active upstream, `api-green` scrape, Redis exporter, PostgreSQL exporter는 후속 운영 관측 보강 항목이다.

## 8. 장애 시나리오

### 8.1 Green readiness 실패

- 장애 상황: Green `/ready`가 503 또는 `status!="ready"`를 반환한다.
- 예상 원인: PostgreSQL 연결 실패, app 설정 오류.
- 사용자 영향: 없음. upstream 전환 전이므로 Blue가 계속 처리한다.
- 탐지 방법: `make deploy-green`, `make deploy-blue-green`.
- 대응 방법: Green 로그와 `/ready` body 확인 후 재배포한다.
- 재발 방지: CI migration/consistency gate와 환경변수 검증을 강화한다.
- README에 기록할 문장: Green readiness 실패 시 Nginx upstream은 전환하지 않고 Blue 트래픽을 유지한다.

### 8.2 Green smoke test 실패

- 장애 상황: HMAC POST, idempotency replay, validation failure smoke 중 하나가 실패한다.
- 예상 원인: API contract 변경, HMAC 설정 누락, idempotency 회귀.
- 사용자 영향: 없음. 전환 전 실패다.
- 탐지 방법: `make deploy-smoke` 또는 `make deploy-blue-green`.
- 대응 방법: smoke 실패 endpoint와 API 로그를 확인한다.
- 재발 방지: Phase 11 consistency/unit test에 회귀 케이스를 추가한다.
- README에 기록할 문장: Green smoke 실패는 배포 중단 조건이며 traffic switch를 수행하지 않는다.

### 8.3 Nginx config test 실패

- 장애 상황: upstream snippet 교체 후 `nginx -t`가 실패한다.
- 예상 원인: 잘못된 snippet, upstream service/port 오타.
- 사용자 영향: 기존 Nginx 설정을 복구하므로 Blue 트래픽 유지.
- 탐지 방법: `docker compose exec -T nginx nginx -t`.
- 대응 방법: script가 이전 snippet을 복원하고 reload하지 않는다.
- 재발 방지: snippet template을 리뷰하고 `bash -n`/config test를 배포 전 수행한다.
- README에 기록할 문장: Nginx config test 실패 시 reload하지 않고 이전 upstream을 유지한다.

### 8.3.1 Nginx reload 실패

- 장애 상황: `nginx -t`는 성공했지만 `nginx -s reload`가 실패한다.
- 예상 원인: Nginx runtime 오류, 컨테이너 상태 이상, reload signal 실패.
- 사용자 영향: 실제 Nginx process는 이전 upstream으로 계속 동작할 수 있다.
- 탐지 방법: deploy script의 reload 실패 로그와 `make deploy-status`.
- 대응 방법: script가 이전 snippet과 `.active-color`를 복구하고 가능한 경우 이전 설정으로 reload를 재시도한다.
- 재발 방지: reload 실패를 성공으로 간주하지 않고 상태 파일과 실제 Nginx 동작의 drift를 방지한다.
- README에 기록할 문장: Nginx reload 실패 시 active upstream 상태를 이전 값으로 복원해 표시 상태와 실제 트래픽 상태가 어긋나지 않게 한다.

### 8.4 전환 후 5xx 급증

- 장애 상황: Green 전환 후 5xx rate가 증가한다.
- 예상 원인: Green runtime 오류, DB/Redis dependency 문제, API contract 회귀.
- 사용자 영향: 일부 요청 실패 가능.
- 탐지 방법: `financial_http_errors_total`, Nginx log, smoke 실패.
- 대응 방법: `make deploy-rollback`으로 Blue upstream 복구 후 `make deploy-verify` 실행.
- 재발 방지: 전환 전 smoke/consistency gate를 보강하고 release checklist에 metric 관찰을 포함한다.
- README에 기록할 문장: 전환 후 5xx가 증가하면 API traffic만 Blue로 rollback하고 DB rollback은 자동화하지 않는다.

### 8.5 전환 후 PostgreSQL 장애

- 장애 상황: PostgreSQL 연결 실패로 `/ready`가 503을 반환한다.
- 예상 원인: DB 장애, connection pool 고갈, migration 문제.
- 사용자 영향: 신규 거래 처리 실패.
- 탐지 방법: `/ready`, `financial_readiness_dependency_status{dependency="postgres"}`.
- 대응 방법: DB 장애를 복구하고, API rollback이 도움이 되는 코드 회귀인지 구분한다.
- 재발 방지: backward-compatible migration과 migration-smoke를 강화한다.
- README에 기록할 문장: PostgreSQL 장애는 Source of Truth 장애이므로 Redis degraded와 달리 readiness 실패로 본다.

### 8.6 Redis degraded 중 배포

- 장애 상황: Redis가 degraded지만 PostgreSQL은 정상이다.
- 예상 원인: Redis down/timeout.
- 사용자 영향: cache/lock 이점 감소, p95/p99 증가 가능.
- 탐지 방법: `/ready mode="degraded"`, `financial_redis_fallback_total`.
- 대응 방법: Phase 10 정책에 따라 배포 자체는 허용 가능하되 5xx 확산 여부를 관찰한다.
- 재발 방지: Redis fallback metric과 duplicate storm 수동 검증을 유지한다.
- README에 기록할 문장: Redis degraded는 단독 배포 차단 사유가 아니지만 5xx 확산은 rollback 조건이다.

### 8.7 rollback 후 정합성 검증 실패

- 장애 상황: Blue rollback 후 `make deploy-verify`에서 중복 Ledger/Event가 발견된다.
- 예상 원인: 배포 중 transaction/idempotency 회귀, 수동 DB 변경.
- 사용자 영향: 금융 정합성 사고 가능.
- 탐지 방법: `tests/k6/sql/verify-consistency.sql`.
- 대응 방법: 추가 트래픽을 중단하고 DB/ledger reconciliation을 수행한다.
- 재발 방지: consistency gate와 deployment smoke를 강화한다.
- README에 기록할 문장: rollback 성공은 트래픽 복구뿐 아니라 PostgreSQL 정합성 검증까지 포함한다.

## 9. 트레이드오프

- Docker Compose vs Kubernetes: Compose는 재현이 쉽지만 service discovery, probe, rollout 기능은 제한적이다.
- Blue-Green vs Rolling: Blue-Green은 rollback 경로가 단순하지만 Blue/Green 리소스를 동시에 사용한다.
- Blue-Green vs Canary: Canary처럼 점진적 트래픽 실험은 어렵지만 포트폴리오 환경에서 절차를 명확히 재현할 수 있다.
- API rollback vs DB rollback: API traffic rollback은 빠르지만 schema rollback은 데이터 손실 위험 때문에 자동화하지 않는다.
- lightweight smoke vs k6 heavy test: 배포 기본 단계는 빠른 smoke를 사용하고, k6 peak/duplicate storm은 수동/릴리즈 전 Gate로 분리한다.
- smoke 데이터: deployment smoke는 실제 Ledger를 생성하므로 운영에서는 `SMOKE_ACCOUNT_NO`로 smoke 전용 계좌를 지정한다.
- migration-smoke 의미: migration을 새로 실행하는 명령이 아니라, 현재 적용된 schema와 주요 unique constraint가 기대와 일치하는지 확인하는 smoke 검증이다.
- Redis degraded 허용 여부: PostgreSQL이 정상이라면 degraded mode를 허용하되, 5xx 확산은 rollback 조건으로 본다.
- 자동 rollback vs 수동 승인: 기본은 `AUTO_ROLLBACK=true`지만 운영 승인 절차가 필요한 환경에서는 false로 전환할 수 있다.

## 10. 면접 답변용 요약

- 왜 Blue-Green을 선택했나요?
  - 금융 이벤트 시스템은 배포 중 정합성 회귀가 치명적이므로, 신규 Green을 검증한 뒤 Nginx upstream만 전환하고 문제가 생기면 Blue로 즉시 되돌릴 수 있는 구조를 선택했다.
- rollback은 어떻게 검증했나요?
  - `make phase12-rollback-check`로 Green 전환 후 Blue rollback, `/health`, `/ready`, smoke, PostgreSQL 정합성 검증 흐름을 재현한다.
- DB migration rollback은 왜 자동화하지 않았나요?
  - 금융 데이터 schema rollback은 데이터 손실 위험이 크므로 API traffic rollback과 DB migration 정책을 분리하고 backward-compatible migration을 원칙으로 삼았다.
- Redis degraded 상태에서 배포를 허용한 이유는 무엇인가요?
  - Phase 10 정책상 Redis는 성능 최적화 계층이고 PostgreSQL이 Source of Truth다. PostgreSQL이 정상이고 Redis만 degraded라면 ready로 보되, Redis 장애가 5xx로 확산되면 rollback 조건으로 본다.
- 배포 전후 정합성은 어떻게 확인했나요?
  - deployment smoke로 HMAC POST와 idempotency replay를 확인하고, `make deploy-verify`로 PostgreSQL duplicate Ledger/Event 0건을 검증한다.
