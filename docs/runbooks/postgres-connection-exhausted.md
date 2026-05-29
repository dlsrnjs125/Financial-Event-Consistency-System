# PostgreSQL Connection Exhausted Runbook

## 1. 증상

- `/ready` 실패 또는 지연
- API 5xx/503 증가
- DB connection wait time 증가
- transaction duration 증가

## 2. 사용자 영향

PostgreSQL은 Source of Truth이므로 연결 고갈 시 신규 거래 처리가 지연되거나 실패할 수 있다. Redis fallback으로 해결할 수 없는 hard dependency 장애다.

## 3. 즉시 확인할 지표

- PostgreSQL active connection count
- connection wait time
- `financial_http_errors_total`
- `financial_db_transaction_retry_total`

## 4. 확인 명령

```bash
curl -i http://localhost:8000/ready
make local-status
make k6-verify
```

## 5. 1차 대응

1. API connection pool 설정 확인
2. 오래 걸리는 transaction 확인
3. 불필요한 부하 테스트 또는 배치 작업 중지
4. DB connection 회복 여부 확인
5. 정합성 검증 SQL 실행

## 6. 복구 확인 기준

- `/ready` 200 회복
- active connection이 정상 범위로 감소
- 5xx/503 증가 중단
- ledger/account 불일치 0건

## 7. 재발 방지

- pool size와 max overflow 재검토
- slow query/lock wait dashboard 추가
- migration과 batch job 실행 시간 분리

## 8. 사후 기록 템플릿

- 발생 시간:
- connection count peak:
- 영향받은 API:
- 복구 명령:
- 정합성 검증 결과:
