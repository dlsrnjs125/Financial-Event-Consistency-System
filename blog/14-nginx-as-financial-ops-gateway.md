# 14편. Nginx Access Control: 운영 endpoint를 public API와 분리하기

## 1. 이번 단계에서 추가한 것은 기능이 아니다

이번 단계의 핵심은 `/metrics`와 `/ready` 몇 개를 숨기는 것이 아니라, public Nginx를 allowlist 방식으로 구성해 외부 거래 API와 내부 운영 endpoint의 노출 경계를 분리한 것이다.

금융 이벤트 시스템에서 외부에 열어야 하는 것은 거래 이벤트 수신 API다. 운영자가 장애 분석에 쓰는 endpoint까지 같은 public 경로로 열 필요는 없다.

```text
외부 금융사 -> public Nginx 8080 -> GET /health, POST /api/v1/transaction-events
운영자/Prometheus -> internal Nginx 8081 -> GET /health, GET /ready, GET /metrics
```

## 2. Public Nginx를 allowlist로 구성한 이유

Public Nginx는 allowlist 방식으로 구성한다. 현재 허용되는 endpoint는 `GET /health`와 `POST /api/v1/transaction-events`뿐이다. 그 외 `/ready`, `/metrics`, `/docs`, `/redoc`, `/openapi.json`, `/nginx_status`, `/admin/*`, `/debug/*`, 정의되지 않은 모든 경로는 Nginx 레벨에서 차단한다.

단순히 `/metrics`만 차단하면 이후 `/docs`, `/openapi.json`, `/debug` 같은 endpoint가 추가됐을 때 다시 public으로 노출될 수 있다. 따라서 public server block은 `GET /health`와 `POST /api/v1/transaction-events`만 허용하고, 정의되지 않은 모든 경로는 기본적으로 404를 반환하도록 구성했다.

![Public 민감 endpoint 차단 확인](./images/ops-phase-3/02-public-sensitive-endpoints-blocked.png)

Public port 8080에서는 `/metrics`, `/ready`, `/docs`, `/openapi.json`이 모두 404를 반환하도록 Nginx 레벨에서 차단했다.

## 3. `/health`, `/ready`, `/metrics`를 다르게 보는 이유

`/health`는 프로세스 생존 여부를 확인하는 최소 공개 endpoint로 유지했다. 반면 `/ready`는 PostgreSQL, Redis 같은 dependency 상태를 포함하고, `/metrics`는 트래픽 패턴, 인증 실패, fallback 여부, 정합성 관련 metric을 노출할 수 있으므로 public endpoint에서 차단했다.

이 프로젝트의 readiness는 PostgreSQL을 hard dependency로 보고, Redis는 degraded dependency로 본다. 즉 `/ready`에는 다음 판단이 들어간다.

- PostgreSQL 연결 가능 여부
- Redis 정상 또는 degraded 여부
- API가 traffic을 받을 준비가 되었는지

이 정보는 배포 시스템과 운영자에게는 필요하지만 외부 클라이언트에게는 필요하지 않다.

## 4. Prometheus 수집 경로는 유지하되 public에서 분리했다

Prometheus 수집 자체를 막은 것이 아니라 scrape 경로를 public `8080/metrics`에서 internal `8081/metrics`로 분리했다. 이를 통해 운영자는 필요한 metric을 계속 수집하면서도 외부 사용자는 metric endpoint에 접근할 수 없게 했다.

![Internal metrics 허용 확인](./images/ops-phase-3/03-internal-metrics-allowed.png)

Metric 수집 자체는 유지하되 public port가 아니라 internal Nginx 경로에서만 `financial_http_requests_total` 같은 custom metric을 확인할 수 있도록 분리했다.

## 5. 구현 방식

Nginx는 같은 upstream snippet을 공유하되 server block을 나눴다.

```text
listen 8080: public traffic
listen 8081: internal operations traffic
```

Blue-Green 전환은 기존처럼 `infra/nginx/conf.d/upstream-active.conf`만 교체한다. Access Control 단계가 배포 전환 구조를 건드리면 rollback 리허설이 깨질 수 있기 때문이다.

Docker Compose에서는 다음처럼 internal port를 loopback에만 bind했다.

```yaml
ports:
  - "8080:8080"
  - "127.0.0.1:8081:8081"
```

Docker Compose 환경에서는 internal port를 `127.0.0.1:8081`에 바인딩해 로컬에서만 접근하도록 제한했다. 실제 운영 환경에서는 이 경로를 VPN, Security Group, internal load balancer, mTLS, Basic Auth 등 추가 보호 계층 뒤에 두어야 한다.

## 6. Access Control 검증 결과

검증은 `make ops3-check-access`와 `make ops3-demo`로 재현한다.

```bash
make ops3-check-access
make ops3-demo
```

![Nginx Access Control 검증 결과](./images/ops-phase-3/01-nginx-access-control-check.png)

Public Nginx에서는 `/ready`, `/metrics`, `/docs`, `/redoc`, `/openapi.json` 등 내부 운영 endpoint가 차단되고, internal Nginx에서는 `/ready`, `/metrics`가 정상 접근되는지 검증했다.

| Endpoint | Public 8080 | Internal 8081 | 판단 |
|---|---:|---:|---|
| `GET /health` | 200 | 200 | PASS |
| `GET /ready` | 404 | 200 | PASS |
| `GET /metrics` | 404 | 200 | PASS |
| `GET /docs` | 404 | - | PASS |
| `GET /redoc` | 404 | - | PASS |
| `GET /openapi.json` | 404 | - | PASS |
| `GET /nginx_status` | 404 | - | PASS |
| `GET /admin/debug` | 404 | - | PASS |
| `GET /debug/vars` | 404 | - | PASS |
| `GET /unknown` | 404 | - | PASS |
| `GET /api/v1/transaction-events` | 403 | - | PASS |
| `POST /api/v1/transaction-events without HMAC` | 400 | - | PASS |
| `POST /api/v1/transaction-events with valid HMAC` | 200 | - | PASS |

## 7. 전체 리허설 결과

`ops3-demo`는 Nginx access control 검증과 public transaction smoke를 함께 실행한다. 민감 endpoint는 public에서 차단되고, 정상 거래 API는 HMAC 인증을 거쳐 기존처럼 동작한다.

![Ops Phase 3 전체 demo 결과](./images/ops-phase-3/04-ops3-demo-public-smoke.png)

이 단계는 “막는 작업”이라서 정상 기능까지 같이 막을 위험이 있다. 그래서 public `/ready`를 막은 뒤에도 다음 회귀를 따로 확인한다.

```bash
make scripts-check
make ops3-demo
make ops2-demo
make final-check
```

Ops Phase 2의 Blue-Green script는 public `/health`와 public transaction smoke를 확인하고, readiness는 internal `8081/ready`로 확인하도록 분리했다.

## 8. 남은 운영 보완점

로컬 Docker Compose의 loopback binding은 접근 제어의 첫 단계일 뿐이다. 실제 운영에서는 internal endpoint를 VPN, 사내망, security group, mTLS, Basic Auth, IP allowlist 같은 추가 경계 뒤에 둬야 한다.

또한 `/health`에 포함된 `deployment_color`, `instance_id`는 Blue-Green 리허설을 위한 로컬 검증 정보다. 운영 환경에서는 public 응답에서 제거하거나, 내부 진단 endpoint 또는 제한된 header로 분리할 수 있다.
