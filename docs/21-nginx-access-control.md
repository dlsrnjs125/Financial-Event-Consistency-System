# Ops Phase 3 - Nginx Access Control

## 1. 문제 정의

이번 단계는 API 기능 추가가 아니라 운영 endpoint의 노출 범위를 분리하는 작업이다.

`/metrics`와 `/ready`가 public Nginx 경로에 노출되면 metric 이름, dependency 상태, Redis degraded 여부, instance identity, 운영 상태가 외부에 드러날 수 있다. 금융 이벤트 시스템에서는 이런 정보도 공격자에게 시스템 구조와 장애 타이밍을 알려주는 단서가 된다.

따라서 public traffic과 internal operations traffic을 Nginx server block과 Docker Compose port binding에서 분리한다.

## 2. `/health`와 `/ready`의 차이

| Endpoint | 의미 | Public 허용 여부 |
|---|---|---|
| `/health` | 프로세스가 살아 있고 reverse proxy가 upstream에 도달 가능한지 확인 | 허용 |
| `/ready` | PostgreSQL hard dependency, Redis degraded 상태 등 운영 의존성 확인 | 차단 |
| `/metrics` | Prometheus metric, internal metric name, readiness/status series 노출 | 차단 |

`/health`는 외부 load balancer나 단순 생존 확인에 사용할 수 있다. 반면 `/ready`는 dependency 상태와 degraded mode를 포함하므로 public endpoint로 열지 않는다.

## 3. Endpoint 정책

### Public Nginx

Public Nginx는 host `8080`에서 접근한다.

Public Nginx는 allowlist 방식으로 구성한다. 현재 허용되는 endpoint는 `GET /health`와 `POST /api/v1/transaction-events`뿐이다. 그 외 `/ready`, `/metrics`, `/docs`, `/redoc`, `/openapi.json`, `/nginx_status`, `/admin/*`, `/debug/*`, 정의되지 않은 모든 경로는 Nginx 레벨에서 차단한다.

허용:

- `GET /health`
- `POST /api/v1/transaction-events`

차단:

- `GET /ready`
- `GET /metrics`
- `GET /docs`
- `GET /redoc`
- `GET /openapi.json`
- `GET /nginx_status`
- allowlist에 없는 `/api/` 하위 경로
- 정의되지 않은 모든 경로
- `/admin/*`, `/debug/*` 같은 내부 운영 경로

무서명 `POST /api/v1/transaction-events` 요청은 기존 HMAC 정책에 따라 실패해야 한다. Nginx access control은 HMAC을 대체하지 않고, application-level 인증 정책을 약화하지 않는다.

### Internal Nginx

Internal Nginx는 container 내부 `8081` listener이며, 로컬 Docker Compose에서는 host loopback에만 bind한다.

```yaml
ports:
  - "8080:8080"
  - "127.0.0.1:8081:8081"
```

허용:

- `GET /health`
- `GET /ready`
- `GET /metrics`
- `GET /nginx_status`

운영 환경에서는 internal port를 public interface에 열지 않고 VPN, 사내망, security group, mTLS, basic auth, allowlist 같은 추가 보호 계층 뒤에 둔다.

## 4. Nginx 구성

`infra/nginx/nginx.conf`는 다음 구조를 사용한다.

- `listen 8080`: public traffic
- `listen 8081`: internal operations traffic
- `include /etc/nginx/conf.d/upstream-active.conf`: 기존 Blue-Green upstream snippet 유지

Blue-Green 전환은 여전히 `infra/nginx/conf.d/upstream-active.conf`만 교체한다. Phase 3는 server block을 분리하지만, active upstream 교체 방식은 바꾸지 않는다.

## 5. Prometheus Scrape 경로

Prometheus는 public `8080/metrics`가 아니라 Docker network 내부의 internal Nginx를 scrape한다.

```yaml
targets:
  - "nginx:8081"
metrics_path: "/metrics"
```

이 설정은 public `/metrics` 차단과 metric 수집을 동시에 만족한다. FastAPI `/metrics` endpoint 자체는 유지하지만 public Nginx에서는 노출하지 않는다.

Ops Phase 3의 `make ops3-demo`는 기본 `docker-compose.yml` 기준으로 public/internal Nginx access control을 검증한다. Ops Phase 1 monitoring overlay는 동일한 internal scrape 원칙을 따르도록 `infra/monitoring/prometheus/prometheus.yml`도 함께 정렬했다.

## 6. 검증 방법

전체 검증:

```bash
make ops3-demo
```

개별 검증:

```bash
make ops3-up
make ops3-nginx-test
make ops3-check-public
make ops3-check-internal
make ops3-check-access
make ops3-smoke-public
```

기대 결과:

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

`scripts/check_nginx_access_control.sh`는 public `/metrics`, `/ready`, `/docs`, `/redoc`, `/openapi.json`, unknown path가 노출되면 실패한다. internal `/metrics`는 200이어야 하며 `financial_http_requests_total` metric을 포함해야 한다.
Valid HMAC transaction smoke는 `make ops3-smoke-public` 또는 `make ops3-demo`의 마지막 단계에서 검증한다.

## 7. 기존 Blue-Green 회귀 기준

Ops Phase 2 명령은 public `/ready`를 더 이상 기대하지 않는다. public Nginx에서는 `/health`와 거래 API smoke를 확인하고, readiness 검증은 `127.0.0.1:8081/ready` internal 경로를 사용한다.

회귀 검증:

```bash
make ops2-demo
make deploy-smoke
```

## 8. 남은 보완점

- 운영 환경에서는 internal port를 host loopback보다 강한 네트워크 경계 뒤에 둔다.
- `/health`의 `deployment_color`, `instance_id`는 로컬 Blue-Green 검증용이다. 운영에서는 내부 진단 endpoint나 제한된 header로 분리할 수 있다.
- Nginx `stub_status`는 internal 경로에서만 허용한다. exporter 연동 시에도 public port로 열지 않는다.
- 실제 운영 TLS termination, mTLS, WAF, VPN, NAC 구성은 별도 운영 환경 과제로 둔다.
