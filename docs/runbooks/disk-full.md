# Disk Full Runbook

## 1. 장애 정의

host filesystem 또는 Docker volume 사용량이 임계치를 초과해 로그 기록, PostgreSQL write, backup 생성이 실패할 수 있는 상태다.

## 2. 사용자 영향

- DB write 실패 가능
- backup 생성 실패 가능
- container log 기록 실패 가능
- 거래 이벤트 처리 실패와 정합성 검증 필요

## 3. 즉시 확인할 Dashboard

- Infra dashboard: disk usage, filesystem available bytes
- PostgreSQL dashboard: write error, checkpoint 상태
- Container dashboard: log size, volume usage

## 4. Alert Rule

```yaml
annotations:
  runbook: "docs/runbooks/disk-full.md"
```

확인할 alert:

- `HostDiskAlmostFull`
- `PostgresWriteError`
- `BackupFailed`

## 5. 1차 확인 명령

```bash
df -h
docker system df
make local-status
```

## 6. 원인 분기표

| 관측 결과 | 판단 | 대응 |
|---|---|---|
| Docker log 급증 | log rotation 미흡 | 오래된 log 정리 |
| backup 파일 증가 | retention 미흡 | cleanup dry-run 후 삭제 |
| PostgreSQL volume 증가 | DB data 증가 | vacuum/보관 정책 검토 |
| filesystem 100% | 즉시 write 위험 | 안전한 임시 파일 정리 |

## 7. 대응 절차

1. disk usage 확인
2. Docker log와 오래된 backup 파일 확인
3. 삭제 가능한 임시 파일만 정리
4. PostgreSQL 정상 write 여부 확인
5. 정합성 검증 SQL 실행

## 8. 복구 확인 기준

- disk usage 정상 범위 회복
- PostgreSQL write 성공
- backup 생성 가능
- ledger/account 검증 통과

## 9. 재발 방지

- backup retention 정책 적용
- log rotation 적용
- disk alert threshold 추가

## 10. 사후 기록 템플릿

- 발생 시간:
- disk usage peak:
- 정리한 파일:
- DB 영향:
- 재발 방지:
