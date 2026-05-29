# PostgreSQL Connection Exhausted Runbook

## 1. 장애 정의

PostgreSQL connection pool 또는 database connection limit에 도달해 API가 DB transaction을 정상적으로 시작하지 못하는 상태다.

PostgreSQL은 Source of Truth이므로 Redis 장애와 달리 hard dependency 장애로 처리한다.

## 2. 사용자 영향

- 신규 거래 이벤트 처리 실패 또는 지연
- `/ready` 실패
- 5xx/503 증가
- client retry 증가로 duplicate request 유입 가능

## 3. 즉시 확인할 Dashboard

- PostgreSQL dashboard: active connection, lock wait, transaction duration
- API dashboard: 5xx/503, DB retry count
- Nginx dashboard: upstream response time

## 4. Alert Rule

```yaml
annotations:
  runbook: "docs/runbooks/postgres-connection-exhausted.md"
```

확인할 alert:

- `PostgresConnectionPressure`
- `PostgresDown`
- `ApiHigh5xxRate`

## 5. 1차 확인 명령

```bash
curl -i http://localhost:8000/ready
make local-status
make k6-verify
```

## 6. 원인 분기표

| 관측 결과 | 판단 | 대응 |
|---|---|---|
| active connection 급증 | pool pressure | 부하/장기 transaction 확인 |
| lock wait 증가 | row lock 병목 | slow transaction 확인 |
| rollback 증가 | transaction conflict | duplicate storm 또는 unique conflict 확인 |
| `/ready` 실패 | hard dependency 장애 | traffic 대상 제외 |

## 7. 대응 절차

1. API connection pool 설정 확인
2. 오래 걸리는 transaction 확인
3. 불필요한 부하 테스트 또는 batch 작업 중지
4. DB connection 회복 여부 확인
5. 정합성 검증 SQL 실행

## 8. 복구 확인 기준

- `/ready` 200 회복
- active connection 정상 범위로 감소
- 5xx/503 증가 중단
- ledger/account 불일치 0건

## 9. 재발 방지

- pool size와 max overflow 재검토
- slow query/lock wait dashboard 추가
- migration과 batch job 실행 시간 분리

## 10. 사후 기록 템플릿

- 발생 시간:
- connection count peak:
- 영향받은 API:
- 복구 명령:
- 정합성 검증 결과:
