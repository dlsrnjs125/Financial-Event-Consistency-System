# 14편. Nginx Access Control: 운영 endpoint를 public API와 분리하기

## 1. 이번 단계에서 추가한 것은 기능이 아니다

이번 단계의 핵심은 API 기능을 추가한 것이 아니라, 운영 endpoint의 노출 범위를 분리한 것이다.

`/health`는 단순 생존 확인이지만 `/ready`와 `/metrics`는 내부 dependency와 서비스 상태를 노출할 수 있으므로 public Nginx에서는 차단하고 internal 경로에서만 접근하도록 구성했다.

금융 이벤트 시스템에서 외부에 열어야 하는 것은 거래 이벤트 수신 API다. 운영자가 장애 분석에 쓰는 endpoint까지 같은 public 경로로 열 필요는 없다.

```text
외부 금융사 -> public Nginx 8080 -> /health, /api/v1/transaction-events
운영자/Prometheus -> internal Nginx 8081 -> /health, /ready, /metrics
```

## 2. `/metrics`를 public으로 열지 않는 이유

Prometheus metric은 단순 숫자처럼 보이지만 시스템 구조를 많이 알려준다.

- 어떤 dependency를 쓰는지
- Redis fallback이 발생했는지
- readiness dependency 이름이 무엇인지
- 어떤 API path와 status가 증가하는지
- 배포 직후 error/latency가 튀는지

공격자는 이런 정보를 보고 장애 타이밍이나 약한 지점을 추측할 수 있다. 그래서 metric 수집은 필요하지만, public reverse proxy에서는 차단해야 한다.

이번 구성에서는 Prometheus가 public `8080/metrics`가 아니라 Docker network 내부의 `nginx:8081/metrics`를 scrape한다.

## 3. `/ready`를 public으로 열지 않는 이유

`/ready`는 `/health`보다 훨씬 많은 운영 정보를 담는다.

이 프로젝트의 readiness는 PostgreSQL을 hard dependency로 보고, Redis는 degraded dependency로 본다. 즉 `/ready`에는 다음 판단이 들어간다.

- PostgreSQL 연결 가능 여부
- Redis 정상 또는 degraded 여부
- API가 traffic을 받을 준비가 되었는지

이 정보는 배포 시스템과 운영자에게는 필요하지만 외부 클라이언트에게는 필요하지 않다. public에는 `/health`만 열어 reverse proxy와 upstream 생존 확인에 사용하고, readiness는 internal 경로로 제한했다.

## 4. 구현 방식

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

로컬에서는 운영자가 `localhost:8081`로 확인할 수 있지만, 운영 환경에서는 이 port를 public interface에 열지 않는 것이 전제다.

## 5. 검증 명령

검증은 `make ops3-demo`로 재현한다.

```bash
make ops3-demo
```

이 명령은 다음을 확인한다.

| Endpoint | Public 8080 | Internal 8081 | 판단 |
|---|---:|---:|---|
| `/health` | 200 | 200 | OK |
| `/ready` | 403/404 | 200 | OK |
| `/metrics` | 403/404 | 200 | OK |
| `/docs`, `/redoc`, `/openapi.json` | 403/404 | not used | OK |
| unknown path | 404 | not used | OK |
| `/api/v1/transaction-events` | HMAC required | not used | OK |

public Nginx는 allowlist 방식이다. 허용되는 endpoint는 `GET /health`와 `POST /api/v1/transaction-events`뿐이며, `/ready`, `/metrics`, `/docs`, `/redoc`, `/openapi.json`, 정의되지 않은 모든 경로는 Nginx 레벨에서 차단한다.

public `/metrics`나 public `/ready`가 200이면 실패한다. 반대로 internal `/metrics`는 200이어야 하고, `financial_http_requests_total` 같은 custom metric을 확인할 수 있어야 한다.

## 6. 기존 Blue-Green 흐름과의 연결

이번 단계는 “막는 작업”이라서 정상 기능까지 같이 막을 위험이 있다.

그래서 public `/ready`를 막은 뒤에도 다음 회귀를 따로 확인한다.

```bash
make ops3-demo
make ops2-demo
make deploy-smoke
```

Ops Phase 2의 Blue-Green script는 public `/health`와 public transaction smoke를 확인하고, readiness는 internal `8081/ready`로 확인하도록 분리했다.

## 7. 남은 운영 보완점

로컬 Docker Compose의 loopback binding은 접근 제어의 첫 단계일 뿐이다. 실제 운영에서는 internal endpoint를 VPN, 사내망, security group, mTLS, basic auth, IP allowlist 같은 추가 경계 뒤에 둬야 한다.

또한 `/health`에 포함된 `deployment_color`, `instance_id`는 Blue-Green 리허설을 위한 로컬 검증 정보다. 운영 환경에서는 public 응답에서 제거하거나, 내부 진단 endpoint 또는 제한된 header로 분리할 수 있다.
