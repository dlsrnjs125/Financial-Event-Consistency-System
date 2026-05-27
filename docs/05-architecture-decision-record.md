# Architecture Decision Record

이 문서는 금융 거래 이벤트 중복 처리 및 정합성 검증 시스템을 설계하면서 내린 주요 기술 선택과 그 배경, 대안, trade-off, 보완 전략을 기록한다.

프로젝트의 목적은 특정 기술을 많이 사용하는 것이 아니라, 금융 이벤트 처리에서 발생할 수 있는 중복 요청, 재시도, 상태 꼬임, 장애 상황에서도 거래 정합성을 유지할 수 있는 구조를 검증하는 것이다.

## ADR-001. Backend Framework: FastAPI

- 선택한 기술:
  - FastAPI

- 고려한 대안:
  - Django REST Framework
  - Spring Boot
  - NestJS

- 선택 배경:
  - 이 프로젝트의 핵심은 복잡한 관리자 기능이나 화면 중심 CRUD가 아니라, 금융 이벤트 수신 API, Idempotency 검증, 상태 머신, Transaction 처리, 장애 재현을 빠르게 구현하고 검증하는 것이다.
  - FastAPI는 Pydantic 기반 요청/응답 검증이 명확하고, OpenAPI 문서가 자동 생성되어 API 계약을 관리하기 쉽다.
  - `/health`, `/ready`, `/metrics` 같은 운영용 endpoint를 구성하기 쉽고, k6 부하 테스트와 Prometheus 연동을 빠르게 진행할 수 있다.
  - Python 기반 테스트 생태계인 pytest와 함께 사용하면 상태 전이, 동시성, 정합성 테스트를 빠르게 작성할 수 있다.

- 기대 효과:
  - API 명세를 빠르게 문서화할 수 있다.
  - 요청 Body 검증과 응답 스키마 관리가 명확하다.
  - 테스트 코드 작성과 실험 반복 속도가 빠르다.
  - 프로젝트 초기에 도메인 로직과 DevOps 검증에 집중할 수 있다.

- 감수한 trade-off:
  - Django REST Framework에 비해 Admin, 인증, ORM 기반 생산성은 상대적으로 약하다.
  - Spring Boot에 비해 금융권 엔터프라이즈 환경에서의 표준성은 낮다.
  - 프로젝트 구조를 직접 잘 잡지 않으면 Router에 비즈니스 로직이 몰릴 수 있다.

- 보완 전략:
  - Router / Service / Repository / Domain 계층을 분리한다.
  - Router는 요청/응답 처리만 담당하고, 정합성 로직은 Service와 Domain 계층에 둔다.
  - SQLAlchemy와 Alembic을 사용해 DB 모델과 Migration을 명확히 관리한다.
  - OpenAPI 문서를 API 계약의 기준으로 삼는다.
  - 테스트 코드에서 상태 머신, Idempotency, Transaction 경계를 반복 검증한다.

- 설계 결론:
  - 이 프로젝트에서는 프레임워크의 완성도보다 금융 이벤트 정합성 로직을 빠르게 구현하고 반복 검증하는 것이 더 중요하다. 따라서 FastAPI를 사용하되, 계층 분리와 테스트 전략을 명확히 가져가는 방식으로 설계한다.

## ADR-002. Database: PostgreSQL

- 선택한 기술:
  - PostgreSQL

- 고려한 대안:
  - MySQL
  - MongoDB
  - Redis only
  - Kafka 기반 이벤트 로그

- 선택 배경:
  - 금융 거래 이벤트는 데이터 정합성, 중복 방지, 상태 이력, 감사 가능성이 중요하다.
  - 동일 이벤트가 여러 번 들어와도 거래가 한 번만 반영되어야 하므로 Unique Constraint와 Transaction이 필수적이다.
  - 잔액 변경은 단순 값 변경이 아니라 LedgerEntry를 통해 추적 가능해야 한다.
  - PostgreSQL은 Transaction, Unique Constraint, Row Lock, Index, JSONB, EXPLAIN 분석 등을 통해 정합성과 성능 실험을 함께 진행하기 적합하다.

- 기대 효과:
  - `external_event_id` 기준 중복 이벤트 저장을 차단할 수 있다.
  - `idempotency_key` 기준 동일 요청의 재처리를 방지할 수 있다.
  - `ledger_entries.transaction_event_id` Unique Constraint로 하나의 이벤트가 원장에 두 번 반영되는 것을 막을 수 있다.
  - Transaction 단위로 이벤트 저장, 상태 전이, 원장 생성, 잔액 변경을 묶을 수 있다.

- 감수한 trade-off:
  - Redis나 NoSQL에 비해 단순 조회/쓰기 속도는 느릴 수 있다.
  - 동시 요청이 몰릴 경우 Lock 경합과 Connection Pool 고갈이 발생할 수 있다.
  - 스키마 변경 시 Migration 전략이 필요하다.
  - 강한 정합성을 얻는 대신 일부 성능 비용을 감수해야 한다.

- 보완 전략:
  - Redis를 Lock/Cache 계층으로 활용해 DB 진입 요청을 줄인다.
  - Connection Pool 지표를 모니터링한다.
  - Slow Query와 Lock 경합을 관측한다.
  - Migration은 Expand -> Backfill -> Contract 전략으로 진행한다.
  - k6로 중복 이벤트 폭주, DB Pool 고갈 상황을 재현한다.

- 설계 결론:
  - 이 시스템에서 최종 정합성 기준은 PostgreSQL이다. Redis나 Application Lock은 보조 수단으로 사용할 수 있지만, 금융 거래가 중복 반영되지 않았다는 최종 보장은 DB Transaction과 Unique Constraint에 둔다.

## ADR-003. Redis Lock/Cache

- 선택한 기술:
  - Redis Lock
  - Redis Cache

- 고려한 대안:
  - PostgreSQL Row Lock만 사용
  - Application Memory Lock
  - Redis 미사용
  - Kafka Consumer 단일 처리

- 선택 배경:
  - 외부 금융 시스템은 타임아웃이나 네트워크 지연으로 동일 이벤트를 짧은 시간에 여러 번 재전송할 수 있다.
  - 모든 중복 요청이 바로 DB Transaction까지 진입하면 DB 부하가 증가한다.
  - Redis를 사용하면 동일 Idempotency Key에 대한 짧은 시간 Lock을 걸거나, 이미 처리된 응답을 캐싱해 빠르게 반환할 수 있다.
  - 다만 Redis는 장애, TTL 만료, 네트워크 단절 가능성이 있기 때문에 최종 정합성 기준으로 삼기에는 위험하다.

- 기대 효과:
  - 동일 이벤트 동시 요청이 DB까지 도달하는 횟수를 줄일 수 있다.
  - 이미 처리된 Idempotency 응답을 빠르게 반환할 수 있다.
  - 외부 시스템의 재시도 폭주 상황에서 API 응답 시간을 줄일 수 있다.
  - Rate Limit 등 확장 기능을 적용하기 쉽다.

- 감수한 trade-off:
  - Redis 장애 시 Lock과 Cache 기능이 동작하지 않는다.
  - Lock TTL이 너무 짧으면 처리 중 Lock이 만료될 수 있다.
  - Lock TTL이 너무 길면 실패 요청이 불필요하게 막힐 수 있다.
  - Redis를 잘못 신뢰하면 정합성 장애로 이어질 수 있다.

- 보완 전략:
  - Redis는 최종 정합성 기준으로 사용하지 않는다.
  - Redis 장애 시 PostgreSQL Transaction과 Unique Constraint로 fallback한다.
  - Lock TTL은 짧게 유지하고, 처리 완료 결과는 DB에 저장한다.
  - Cache Miss나 Redis Down 상황도 정상 처리 흐름으로 간주한다.
  - Redis 장애 시나리오를 Docker Compose와 k6로 재현한다.

- 설계 결론:
  - Redis는 금융 정합성을 보장하는 주체가 아니라, 중복 요청을 완화하고 응답 속도를 개선하는 보조 계층이다. Redis가 없어도 중복 거래 반영은 PostgreSQL에서 막을 수 있어야 한다.

## ADR-004. Queue/Kafka를 Phase 1에서 제외한 이유

- 선택한 방식:
  - Phase 1에서는 동기 API 처리 구조를 사용한다.
  - Queue, Kafka, Redis Stream은 초기 구현 범위에서 제외한다.

- 고려한 대안:
  - Kafka
  - RabbitMQ
  - Redis Stream
  - Celery Worker

- 선택 배경:
  - 이 프로젝트의 1차 목표는 대규모 이벤트 스트리밍 플랫폼을 만드는 것이 아니라, 금융 이벤트 중복 처리와 정합성 검증을 명확히 재현하는 것이다.
  - Queue를 도입하면 Consumer 재처리, Offset 관리, DLQ, 메시지 순서 보장, Exactly-once 유사 처리 등 별도의 설계 문제가 추가된다.
  - 초기 단계에서 Queue를 도입하면 Idempotency, Transaction, 상태 머신이라는 핵심 주제가 흐려질 수 있다.
  - 따라서 먼저 동기 API 구조에서 외부 시스템의 재시도와 중복 요청 문제를 직접 다룬다.

- 기대 효과:
  - 시스템 구조를 단순하게 유지할 수 있다.
  - 중복 처리와 상태 전이 검증에 집중할 수 있다.
  - Transaction 경계를 명확하게 정의할 수 있다.
  - 장애 재현과 테스트 작성이 쉬워진다.

- 감수한 trade-off:
  - 순간 트래픽을 Queue로 흡수하지 못한다.
  - 비동기 재처리 구조가 없다.
  - DLQ 기반 실패 이벤트 관리가 없다.
  - 장기적으로 대량 이벤트 처리에는 한계가 있다.

- 보완 전략:
  - 실패 이벤트는 DB 상태로 기록한다.
  - API 요청 실패 시 외부 시스템 재시도와 Idempotency로 처리한다.
  - Event Processing Service를 분리해 추후 Worker나 Queue로 이동할 수 있게 한다.
  - Phase 2 확장 후보로 Redis Stream 또는 Kafka를 남겨둔다.

- 설계 결론:
  - Phase 1에서는 Queue를 도입하지 않고, 동기 API 구조에서 Idempotency와 DB Transaction 기반 정합성을 먼저 완성한다. Queue는 확장성 문제를 다룰 단계에서 별도로 검토한다.

## ADR-005. Architecture: Modular Monolith

- 선택한 구조:
  - 단일 FastAPI 애플리케이션
  - 내부 계층 분리: Router / Service / Repository / Domain

- 고려한 대안:
  - MSA
  - Event-Driven Architecture
  - Serverless Architecture

- 선택 배경:
  - 현재 프로젝트의 핵심은 서비스 분산보다 거래 정합성 규칙을 명확히 정의하고 검증하는 것이다.
  - MSA를 적용하면 서비스 간 네트워크 실패, 분산 트랜잭션, Saga, 메시지 중복 소비 같은 문제가 추가된다.
  - 아직 도메인 경계가 완전히 안정되지 않은 상태에서 서비스를 나누면 구조가 과도하게 복잡해질 수 있다.
  - 단일 애플리케이션 안에서 도메인 모듈을 분리하면 구현 복잡도를 낮추면서도 추후 확장 가능성을 유지할 수 있다.

- 기대 효과:
  - Transaction 경계를 단일 DB 기준으로 명확하게 유지할 수 있다.
  - 테스트와 장애 재현이 단순해진다.
  - 초기 개발 속도가 빠르다.
  - 도메인 모델이 안정된 이후 서비스 분리를 검토할 수 있다.

- 감수한 trade-off:
  - 서비스별 독립 배포가 어렵다.
  - 특정 모듈 장애가 전체 API에 영향을 줄 수 있다.
  - 팀 규모가 커질 경우 코드 경계 관리가 중요해진다.
  - 트래픽이 크게 증가하면 일부 기능만 독립 확장하기 어렵다.

- 보완 전략:
  - 도메인 로직을 Service와 Domain 계층에 격리한다.
  - 인프라 의존성은 Repository, Client 계층으로 제한한다.
  - 이벤트 처리 로직은 추후 Worker로 분리 가능한 형태로 작성한다.
  - 모듈 간 직접 참조를 최소화한다.

- 설계 결론:
  - Phase 1에서는 Modular Monolith로 시작한다. 이는 단순한 단일 애플리케이션이 아니라, 도메인 경계와 책임을 내부적으로 분리한 구조이며, 정합성 검증을 우선 완성하기 위한 선택이다.

## ADR-006. Local Infra: Docker Compose

- 선택한 기술:
  - Docker Compose

- 고려한 대안:
  - 로컬 직접 설치
  - Kubernetes
  - Minikube
  - Docker Swarm

- 선택 배경:
  - 이 프로젝트는 PostgreSQL, Redis, API Server, Nginx, Prometheus, Grafana를 함께 실행해야 한다.
  - Docker Compose를 사용하면 전체 실행 환경을 코드로 관리할 수 있고, 장애 재현을 반복하기 쉽다.
  - Redis Down, DB Restart, API Restart, Nginx 전환 같은 실험을 로컬에서 빠르게 수행할 수 있다.
  - 프로젝트를 검토하는 사람도 복잡한 설치 없이 동일한 환경을 실행할 수 있다.

- 기대 효과:
  - 실행 환경 재현성이 높아진다.
  - 장애 주입 테스트가 쉬워진다.
  - 개발/테스트/문서화 흐름을 하나로 연결할 수 있다.
  - Prometheus/Grafana까지 포함한 관측 환경을 로컬에서 검증할 수 있다.

- 감수한 trade-off:
  - 실제 Kubernetes 운영 환경과는 차이가 있다.
  - Auto Scaling, Rolling Update, Self-Healing 같은 기능은 제한적이다.
  - 운영 수준의 Secret 관리나 네트워크 정책을 완전히 재현하기 어렵다.

- 보완 전략:
  - Docker Compose는 장애 재현과 로컬 운영 검증 목적으로 사용한다.
  - Blue-Green 배포는 Nginx upstream 전환으로 시뮬레이션한다.
  - Kubernetes는 Phase 3 확장 항목으로 분리한다.
  - README에 Docker Compose 환경의 목적과 한계를 명시한다.

- 설계 결론:
  - 이 프로젝트에서 Docker Compose는 단순 실행 도구가 아니라, 금융 이벤트 처리 시스템의 장애 상황을 반복적으로 재현하고 검증하기 위한 로컬 운영 환경이다.

## ADR-007. Deployment Strategy: Blue-Green

- 선택한 전략:
  - Blue-Green 배포 시뮬레이션

- 고려한 대안:
  - Rolling Deployment
  - Canary Deployment
  - Recreate Deployment

- 선택 배경:
  - 금융 이벤트 처리 시스템에서는 신규 버전 배포 전 정합성 검증이 중요하다.
  - Blue-Green 구조에서는 기존 Blue 버전을 유지한 상태에서 Green 버전을 먼저 실행하고, `/health`, `/ready`, Smoke Test, Consistency Test를 통과한 뒤 트래픽을 전환할 수 있다.
  - 문제가 발생하면 Nginx upstream을 다시 Blue로 되돌리는 방식으로 rollback 경로가 명확하다.

- 기대 효과:
  - 신규 버전을 운영 트래픽에 노출하기 전에 검증할 수 있다.
  - rollback 절차가 단순하다.
  - 배포 전후 메트릭 비교가 쉽다.
  - 장애 상황을 시뮬레이션하기 좋다.

- 감수한 trade-off:
  - Blue와 Green을 동시에 띄우기 때문에 리소스 사용량이 증가한다.
  - DB Migration이 포함되면 단순 rollback이 어려울 수 있다.
  - 두 버전이 같은 DB를 사용할 경우 backward compatibility가 필요하다.
  - Canary처럼 일부 트래픽만 점진적으로 보내는 실험은 어렵다.

- 보완 전략:
  - DB Migration은 backward-compatible하게 설계한다.
  - Green 전환 전 정합성 테스트를 수행한다.
  - 배포 후 p95 latency, 5xx error rate, invalid state transition, duplicate event 지표를 모니터링한다.
  - rollback 조건을 문서화한다.

- 설계 결론:
  - 이 프로젝트에서는 배포 속도보다 검증 가능한 전환과 rollback 가능성이 중요하다. 따라서 Docker Compose와 Nginx를 사용해 Blue-Green 배포 흐름을 시뮬레이션한다.

## ADR-008. CI/CD: GitHub Actions

- 선택한 기술:
  - GitHub Actions

- 고려한 대안:
  - Jenkins
  - GitLab CI
  - CircleCI

- 선택 배경:
  - GitHub 저장소와 자연스럽게 연동된다.
  - PR 단위로 테스트를 자동 실행하기 쉽다.
  - Secret 관리, Docker Build, 테스트 실행, 배포 스크립트 실행을 하나의 workflow로 구성할 수 있다.
  - 이 프로젝트에서는 단순 빌드 성공보다 정합성 테스트를 CI Gate로 사용하는 것이 중요하다.

- 기대 효과:
  - PR 단계에서 잘못된 상태 전이, 중복 이벤트 처리 실패, Migration 오류를 조기에 발견할 수 있다.
  - main 브랜치에 정합성을 깨는 코드가 들어가는 것을 막을 수 있다.
  - 배포 전 자동 검증 절차를 명확히 만들 수 있다.
  - Secret을 저장소에 직접 커밋하지 않고 관리할 수 있다.

- 감수한 trade-off:
  - Jenkins에 비해 복잡한 커스텀 파이프라인 구성은 제한적일 수 있다.
  - 사내망이나 폐쇄망 환경을 재현하기는 어렵다.
  - GitHub Actions 사용량 제한이나 실행 환경 제약이 있을 수 있다.

- 보완 전략:
  - Workflow를 CI와 Deploy로 분리한다.
  - CI 단계에는 Lint, Unit Test, Integration Test, Consistency Test, Migration Test, Docker Build, Secret Scan을 포함한다.
  - 배포 단계에서는 Green 배포 후 Health Check와 Smoke Test를 수행한다.
  - GitHub Secrets와 `.env.example`을 분리해 관리한다.

- 설계 결론:
  - GitHub Actions는 이 프로젝트에서 단순 자동화 도구가 아니라, 금융 이벤트 정합성을 깨는 코드가 배포되지 않도록 막는 검증 경계로 사용한다.

## ADR-009. External API Authentication: HMAC Signature

- 선택한 방식:
  - 외부 시스템 API Key + HMAC Signature 검증

- 고려한 대안:
  - 단순 API Key
  - JWT
  - OAuth2 Client Credentials
  - mTLS

- 선택 배경:
  - 이 프로젝트의 이벤트 수신 API는 일반 사용자가 호출하는 API가 아니라 외부 금융 시스템이 호출하는 시스템 간 API다.
  - 단순 API Key만 사용하면 키가 탈취되었을 때 요청 위조를 막기 어렵다.
  - HMAC Signature를 사용하면 요청 Body, Timestamp, Secret을 기반으로 서명을 검증할 수 있어 요청 변조와 일부 Replay Attack을 줄일 수 있다.
  - mTLS나 OAuth2는 더 강한 방식이지만 Phase 1에서는 구현 복잡도가 높다.

- 기대 효과:
  - 요청 Body 변조 여부를 검증할 수 있다.
  - Timestamp를 통해 오래된 요청 재사용을 제한할 수 있다.
  - 외부 시스템별 Secret을 분리할 수 있다.
  - 인증 실패 로그를 구조화해 추적할 수 있다.

- 감수한 trade-off:
  - Secret 관리가 중요해진다.
  - 클라이언트와 서버가 동일한 서명 규칙을 공유해야 한다.
  - Timestamp 오차 허용 범위를 설계해야 한다.
  - 완전한 Replay Attack 방지를 위해 nonce 저장이 추가로 필요할 수 있다.

- 보완 전략:
  - `X-Client-Id`, `X-Timestamp`, `X-Signature` Header를 사용한다.
  - Timestamp 허용 범위를 5분 이내로 제한한다.
  - Signature 검증 실패 시 요청 Body를 처리하지 않는다.
  - Secret은 GitHub Secrets 또는 서버 환경변수로 관리한다.
  - 요청 로그에는 Secret이나 원본 Signature를 남기지 않는다.

- 설계 결론:
  - Phase 1에서는 외부 시스템 인증을 위해 HMAC Signature 방식을 사용한다. 단순 API Key보다 요청 변조 방어에 유리하고, mTLS나 OAuth2보다 구현 복잡도가 낮아 현재 프로젝트 범위에 적합하다.

## ADR-010. Observability: Prometheus, Grafana, Structured Logging

- 선택한 기술:
  - Prometheus
  - Grafana
  - JSON Structured Logging

- 고려한 대안:
  - CloudWatch
  - ELK Stack
  - Datadog
  - 단순 파일 로그

- 선택 배경:
  - 이 프로젝트에서는 단순 서버 상태보다 거래 이벤트 정합성 상태를 관측하는 것이 중요하다.
  - 중복 이벤트 수, Idempotency Hit Ratio, 잘못된 상태 전이 수, DB Connection Pool 사용률 같은 도메인 지표를 직접 정의해야 한다.
  - Prometheus와 Grafana는 로컬 Docker Compose 환경에서 쉽게 구성할 수 있고, 메트릭 기반 대시보드와 Alert Rule 설계에 적합하다.
  - 구조화 로그를 사용하면 `trace_id`, `request_id`, `event_id`, `idempotency_key` 기준으로 이벤트 흐름을 추적할 수 있다.

- 기대 효과:
  - API 성능과 도메인 정합성 지표를 함께 확인할 수 있다.
  - 장애 발생 시 어느 계층에서 문제가 발생했는지 추적할 수 있다.
  - 배포 전후 지표를 비교할 수 있다.
  - 기술 블로그에서 실험 결과를 수치로 보여줄 수 있다.

- 감수한 trade-off:
  - 메트릭 설계와 로그 필드 설계가 필요하다.
  - Prometheus/Grafana 운영 구성이 추가된다.
  - 로그가 과도하게 많아지면 저장 비용과 분석 비용이 증가할 수 있다.
  - 개인정보 마스킹을 놓치면 보안 문제가 생길 수 있다.

- 보완 전략:
  - 메트릭은 API 메트릭, DB 메트릭, Redis 메트릭, 도메인 메트릭으로 구분한다.
  - 로그에는 계좌번호, 토큰, Secret을 남기지 않는다.
  - 모든 요청에 `request_id`를 부여한다.
  - 거래 이벤트 처리 흐름에는 `trace_id`, `event_id`, `external_event_id`, `idempotency_key`를 포함한다.
  - Alert Rule은 단순 CPU 기준이 아니라 정합성 관련 지표도 포함한다.

- 설계 결론:
  - 이 프로젝트의 관측성은 서버가 살아 있는지 확인하는 수준을 넘어서, 금융 이벤트가 중복 없이 정확히 처리되고 있는지 확인하는 데 초점을 둔다.
