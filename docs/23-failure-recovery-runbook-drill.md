# Ops Phase 5 - Failure Recovery Runbook Drill

## 1. 왜 장애 복구 Runbook Drill이 필요한가

금융 이벤트 시스템의 장애 대응은 "복구 명령을 알고 있다"에서 끝나면 안 된다.
장애 주입, 영향 확인, 복구 명령 실행, 서비스 정상성 확인, PostgreSQL 기준
정합성 검증, evidence report 생성까지 같은 흐름으로 반복할 수 있어야 한다.

Ops Phase 5의 목표는 Redis/API/PostgreSQL 장애를 Docker Compose 환경에서 실제로
재현하고, 복구 후 health/ready/smoke/consistency 결과와 recovery duration을
count-only evidence로 남기는 것이다.

## 2. 장애 시나리오

| 시나리오 | 장애 주입 | 핵심 검증 |
|---|---|---|
| Redis failure recovery | `docker compose stop redis` | Redis degraded 상태에서도 PostgreSQL 기준 중복 반영 0건 |
| API failure recovery | `docker compose stop api-blue` | health 실패 감지 후 API 재기동, health/ready/smoke PASS |
| PostgreSQL failure detection/recovery | `docker compose stop postgres` | `/ready` 실패 감지 후 DB 재기동, readiness 및 consistency PASS |

PostgreSQL 장애는 데이터 손상 위험이 있으므로 volume 삭제, DB 초기화, restore
덮어쓰기 같은 destructive operation을 사용하지 않는다.

## 3. 장애 주입과 복구 명령

```bash
make ops5-up
make ops5-check
make ops5-redis-drill
make ops5-api-drill
make ops5-db-drill
make ops5-drill
make ops5-demo
```

`make ops5-demo`는 스택 기동, 사전 점검, 전체 drill 실행, report 출력까지
한 번에 수행한다.

## 4. 검증 기준

Redis 장애 복구:

- Redis down 감지
- `/ready`에서 Redis degraded 확인
- Redis down 중 동일 요청 2회 처리
- 동일 `external_event_id` 기준 event 1건, ledger 1건, idempotency record 1건
- Redis 재기동 후 `/ready` PASS
- 전체 consistency count 0

API 장애 복구:

- API down 감지
- `/health` 실패 확인
- API 재기동
- `/health`, `/ready` PASS
- 복구 후 smoke request PASS

PostgreSQL 장애 감지/복구:

- DB down 상태에서 `/ready` FAIL
- DB 재기동
- `/ready` PASS
- 복구 후 consistency count 0

## 5. Recovery Duration 측정 기준

각 시나리오는 장애 주입 직전부터 복구 후 마지막 검증이 끝나는 시점까지를
duration seconds로 기록한다.
전체 drill duration은 스크립트 시작부터 report 작성 직전까지의 시간이다.

이 수치는 대규모 운영 환경의 공식 RTO가 아니라, 로컬 Docker Compose runbook이
얼마나 빠르게 장애를 탐지하고 복구 절차를 끝내는지 보여주는 evidence다.

## 6. Count-only Evidence 정책

Report에는 다음만 기록한다.

- PASS/FAIL
- recovery duration seconds
- duplicate ledger/idempotency violation count
- consistency check 결과

Report에는 실제 거래 row data, account number 원문 목록, secret, token, dump 파일
내용을 기록하지 않는다.

## 7. CI Trade-off

Ops Phase 5의 장애 주입 Drill은 Docker Compose 컨테이너 stop/start를 포함하므로
로컬 운영 Drill로 수행한다. CI에서는 스크립트 문법과 report 포맷을 검증하고,
실제 복구 evidence는 `reports/ops/ops5-failure-recovery-drill.md`에 기록한다.

이 선택은 CI flakiness를 줄이기 위한 것이다. 컨테이너 stop/start는 runner 상태,
네트워크 타이밍, 이미지 pull 시간에 영향을 받기 쉽다. 대신 로컬 evidence report를
curated artifact로 남기고, PR Gate는 실행 가능한 runbook과 report 형식을 검증한다.

## 8. README에 요약할 문장

Ops Phase 5에서는 Redis/API/PostgreSQL 장애를 Docker Compose 환경에서 stop/start
방식으로 재현하고, 복구 후 health/ready/smoke/consistency check와 recovery
duration을 `reports/ops/ops5-failure-recovery-drill.md`에 count-only evidence로
남긴다.
