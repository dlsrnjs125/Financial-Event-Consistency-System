# Phase 11 - CI/CD Deployment Gate Hardening

## 1. 목적

Phase 11은 GitHub Actions를 새로 도입하는 단계가 아니라, 기존 CI를 금융 이벤트 정합성 배포 Gate로 고도화하는 단계다.
로컬에서 사람이 실행하던 `make final-check`, `make security-log-check`, consistency test, migration test를 PR Gate와 연결해 main 병합 전 회귀를 자동 차단한다.

이 프로젝트의 배포 Gate는 단순 빌드 성공보다 다음 위험을 먼저 막는다.

- 동일 이벤트 또는 동일 idempotency key의 중복 반영
- 잘못된 상태 전이 허용
- PostgreSQL migration 실패
- 운영 로그에 raw 민감 필드 노출
- 저장소 secret 유출
- 배포 Docker image 생성 실패

## 2. Gate 구성

| Gate | Job | 검증 내용 | 실패 시 의미 |
|---|---|---|---|
| Format/Lint | `lint` | `black --check`, `isort --check-only`, `flake8`, `ruff check` | 기본 품질 또는 정적 오류 실패 |
| Unit Test | `unit-tests` | `backend/tests/unit` 도메인/서비스 단위 검증 | 핵심 로직 회귀 |
| Consistency Test | `consistency-tests` | PostgreSQL + Redis service container 기반 consistency, idempotency, 상태 전이 회귀 검증 | 금융 정합성 위험 |
| Migration Test | `migration-tests` | PostgreSQL에서 `alembic upgrade head`, revision, unique constraint smoke check | 배포 시 DB 장애 위험 |
| Security Log Check | `security-log-check` | backend app 구조화 로그의 raw 민감 필드 차단 | 개인정보/보안 위험 |
| Secret Scan | `secret-scan` | TruffleHog repository secret scan | credential leak 위험 |
| Docker Build | `docker-build` | `backend/Dockerfile` image build와 inspect | 배포 artifact 생성 실패 |
| Gate Check | `gate-check` | 모든 필수 job 결과 종합 | merge 차단 |

## 3. PR Gate와 Performance Test 분리 이유

k6 duplicate storm, Redis Down duplicate storm, peak load는 정합성 검증에 중요하지만 PR마다 실행하기에는 비용과 시간이 크다.
따라서 PR Gate는 빠른 feedback이 가능한 unit/consistency/migration/security/docker 검증을 필수로 수행하고, k6는 수동 local gate, 릴리즈 전 성능 gate, 또는 nightly workflow 후보로 분리한다.

이 분리는 정합성 회귀는 빠르게 차단하면서도 p95/p99/RPS 같은 운영 성능 수치는 충분한 환경에서 별도로 측정하기 위한 선택이다.

## 4. 실패 시 대응 가이드

| 실패 Gate | 대응 방법 |
|---|---|
| lint | `make format-check`, `make lint`를 로컬에서 재현하고 `make format`으로 정리한다. |
| unit-tests | `pytest backend/tests/unit -v`로 실패 테스트를 재현하고 도메인 규칙 회귀 여부를 확인한다. |
| consistency-tests | PostgreSQL unique constraint, idempotency record, 상태 전이, Redis fallback 경로를 우선 확인한다. |
| migration-tests | `alembic upgrade head` 실패 원인과 unique constraint smoke check 실패 테이블을 확인한다. |
| security-log-check | raw `idempotency_key`, `account_no`, `signature`, `secret`, `raw_body`, `password`, `token` logging을 masked field로 바꾼다. |
| secret-scan | 실제 credential이면 즉시 폐기/rotation하고, 더미 값이면 `.env.example` 형태로 안전하게 표현한다. |
| docker-build | `docker build -t financial-events:test ./backend`로 로컬 재현 후 Dockerfile dependency와 entrypoint를 확인한다. |

## 5. 로컬 재현 명령

```bash
make ci-local
make final-check
make security-log-check
make migration-smoke
make k6-verify
make phase10-redis-down-check
```

`make ci-local`은 GitHub Actions의 빠른 로컬 대응 명령이며 unit test 중심으로 실행한다.
PostgreSQL/Redis service container 기반 consistency gate, migration gate, Docker build gate는 GitHub Actions에서 최종 확인한다.
로컬에서 migration constraint smoke check를 재현하려면 `DATABASE_URL`이 빈 PostgreSQL DB를 가리키는 상태에서 `alembic upgrade head` 후 `make migration-smoke`를 실행한다.

## 6. 트레이드오프

- 모든 테스트를 PR Gate에 넣지 않는다. 빠른 feedback을 위해 k6 부하 테스트는 수동/야간/릴리즈 전 Gate로 분리한다.
- `security-log-check`는 구조화 로그 정책 검사이고, `secret-scan`은 저장소 credential 유출 검사다. 둘은 서로 대체하지 않는다.
- Secret scan action은 CI 재현성을 위해 floating ref(`@main`)가 아닌 version tag(`@v3`)로 고정한다.
- TruffleHog는 PR Gate 안정성을 위해 `--only-verified`를 사용한다. 오탐은 줄어들지만, unverified secret-like pattern 탐지는 별도 강화 후보로 남긴다.
- GitHub Actions service container는 PR마다 깨끗한 PostgreSQL/Redis를 제공하지만, 로컬 Docker Compose의 Nginx/Prometheus/Grafana 전체 스택과 완전히 같지는 않다.
- migration downgrade는 이번 Gate에 포함하지 않는다. 금융 데이터 migration rollback은 별도 backward-compatible migration 정책으로 다룬다.
- Docker container 실행 smoke test는 Phase 12 Blue-Green/Rollback 시뮬레이션에서 health check 기반으로 확장한다.

## 7. README에 넣을 요약 문장

Phase 11에서는 기존 GitHub Actions CI를 금융 이벤트 정합성 배포 Gate로 고도화했다. PR 병합 전 format/lint, unit test, PostgreSQL+Redis consistency test, PostgreSQL migration test, security-log-check, secret scan, Docker build를 통과해야 하며, k6 부하 테스트는 PR 필수 Gate가 아닌 수동/릴리즈 전 성능 Gate로 분리했다.
