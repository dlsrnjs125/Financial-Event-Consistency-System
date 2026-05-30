# Ops Phase 5 - Failure Recovery Runbook Drill

## 실행 목적

Redis, API, PostgreSQL 장애를 Docker Compose 로컬 운영 환경에서 재현하고, 복구 후 서비스 정상성 및 PostgreSQL 기준 정합성을 count-only evidence로 남긴다.

## 실행 환경

| 항목 | 값 |
|---|---|
| 실행 명령 | `SCENARIO=all ./scripts/ops5_failure_recovery_drill.sh` |
| 시작 시각 UTC | `2026-05-30T18:06:39Z` |
| 종료 시각 UTC | `2026-05-30T18:06:55Z` |
| Public base URL | `http://localhost:8080` |
| Readiness base URL | `http://localhost:8081` |
| API service | `api-blue` |
| PostgreSQL service | `postgres` |
| Redis service | `redis` |

## 결과 요약

| 시나리오 | 결과 | 복구 시간 seconds | 주요 검증 |
|---|---:|---:|---|
| Redis failure recovery | PASS | 2 | fallback + consistency |
| API failure recovery | PASS | 10 | health/ready + smoke |
| PostgreSQL failure detection/recovery | PASS | 3 | readiness fail/pass + consistency |

## Redis Failure Recovery Evidence

| 항목 | 결과 |
|---|---|
| Redis down detected | PASS |
| Redis ready state while down | degraded |
| API fallback behavior | PASS |
| Event count for duplicate smoke | 1 |
| Ledger count for duplicate smoke | 1 |
| Idempotency record count for duplicate smoke | 1 |
| Redis restarted | PASS |
| Ready after recovery | PASS |
| Consistency check | PASS |
| Duplicate ledger count | 0 |
| Idempotency violation count | 0 |

## API Failure Recovery Evidence

| 항목 | 결과 |
|---|---|
| API down detected | PASS |
| Health check failure detected | PASS |
| API restarted | PASS |
| Health after recovery | PASS |
| Ready after recovery | PASS |
| Smoke request after recovery | PASS |

## PostgreSQL Failure Recovery Evidence

| 항목 | 결과 |
|---|---|
| DB down detected by readiness | PASS |
| DB restarted | PASS |
| Ready after recovery | PASS |
| Consistency check after recovery | PASS |

## 복구 시간 Evidence

| 항목 | 값 |
|---|---:|
| Redis recovery duration seconds | 2 |
| API recovery duration seconds | 10 |
| DB recovery duration seconds | 3 |
| Total drill duration seconds | 16 |

## 운영상 한계와 보완 전략

- 이 drill은 운영 DB volume을 삭제하지 않고 Docker Compose `stop/start`만 사용한다.
- PostgreSQL 장애는 destructive restore가 아니라 readiness failure detection과 재기동 후 정합성 확인으로 제한한다.
- Redis 장애는 최종 정합성 실패가 아니라 degraded dependency로 취급하며, PostgreSQL unique constraint와 transaction을 최종 기준으로 검증한다.
- 컨테이너 stop/start는 CI 환경에서 flakiness가 생길 수 있으므로 실제 장애 주입 evidence는 로컬 runbook drill report로 관리하고, CI에서는 스크립트 문법과 report format을 검증한다.
- Report에는 실제 거래 row data, account_no 원문 목록, secret, token, dump 내용이 아니라 PASS/FAIL, duration, count-only 결과만 기록한다.

## README에 기록할 문장

Ops Phase 5에서는 Redis/API/PostgreSQL 장애를 Docker Compose 환경에서 stop/start 방식으로 재현하고, 복구 후 health/ready/smoke/consistency check와 recovery duration을 `reports/ops/ops5-failure-recovery-drill.md`에 count-only evidence로 남긴다.
