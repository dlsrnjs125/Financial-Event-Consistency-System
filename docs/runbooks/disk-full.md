# Disk Full Runbook

## 1. 증상

- disk usage 90% 이상
- PostgreSQL write 실패 가능
- Docker log 증가
- backup 생성 실패

## 2. 사용자 영향

DB write가 실패하면 거래 이벤트 처리가 실패할 수 있다. 로그와 백업도 중단될 수 있으므로 빠른 용량 확보와 정합성 검증이 필요하다.

## 3. 즉시 확인할 지표

- node filesystem usage
- container log size
- PostgreSQL write error
- backup script failure count

## 4. 확인 명령

```bash
df -h
docker system df
make local-status
```

## 5. 1차 대응

1. disk usage 확인
2. Docker log와 오래된 backup 파일 확인
3. 삭제 가능한 임시 파일만 정리
4. PostgreSQL 정상 write 여부 확인
5. 정합성 검증 SQL 실행

## 6. 복구 확인 기준

- disk usage 정상 범위 회복
- PostgreSQL write 성공
- backup 생성 가능
- ledger/account 검증 통과

## 7. 재발 방지

- backup retention 정책 적용
- log rotation 적용
- disk alert threshold 추가

## 8. 사후 기록 템플릿

- 발생 시간:
- disk usage peak:
- 정리한 파일:
- DB 영향:
- 재발 방지:
