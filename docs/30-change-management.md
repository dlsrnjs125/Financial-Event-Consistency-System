# Change Management

## 1. 목적

운영에서는 장애 대응만큼 변경을 안전하게 반영하는 절차가 중요하다.

이 문서는 config, application deployment, DB migration, Nginx routing, secret rotation, backup/restore 변경의 사전/사후 검증 기준을 정의한다.

## 2. 변경 유형

| 변경 유형 | 예시 |
|---|---|
| Config change | environment variable, timeout, pool size |
| App deployment | API image 배포 |
| DB migration | Alembic revision 적용 |
| Nginx routing change | Blue/Green upstream 전환 |
| Secret rotation | HMAC secret 교체 |
| Backup/restore operation | DR Drill, restore test |

## 3. 변경 전 체크리스트

- `make final-check` 통과
- rollback 경로 확인
- DB migration 영향 확인
- migration 전 backup 필요 여부 확인
- 영향 endpoint 확인
- 관련 runbook 확인
- alert silence 필요 여부 확인

## 4. 변경 후 검증

```bash
make health
make ready
make deploy-smoke
make deploy-verify
make k6-smoke
```

검증 기준:

- `/health` 200
- `/ready` 200 또는 Redis degraded 허용
- smoke test 통과
- duplicate ledger/event count 0
- p95/p99 급증 없음
- error rate 급증 없음

## 5. DB Migration 운영 기준

- destructive migration은 기본 금지
- expand -> backfill -> contract 순서 권장
- migration 전 backup 수행
- migration 후 정합성 SQL 실행
- rollback은 schema rollback보다 traffic rollback을 우선

## 6. Time Sync 운영 기준

HMAC timestamp, replay 방지, log correlation, incident timeline에는 시간 동기화가 중요하다.

- 모든 container log는 UTC 또는 KST 중 하나로 통일한다.
- timestamp는 ISO-8601 형식을 사용한다.
- HMAC timestamp 허용 오차는 예: ±5분으로 둔다.
- 서버 clock drift가 커지면 replay 검증 오탐이 발생할 수 있다.
- incident report에는 detection_time, mitigation_time, recovery_time을 분리 기록한다.
