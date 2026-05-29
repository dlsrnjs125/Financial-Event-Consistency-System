# Backup Restore Failed Runbook

## 1. 장애 정의

백업 파일 생성, checksum 검증, restore DB 복원, restore 후 정합성 검증 중 하나가 실패한 상태다.

복구 가능성 자체가 훼손될 수 있으므로 SEV2로 시작하고, 운영 DB 손상과 결합되면 SEV1으로 격상한다.

## 2. 사용자 영향

- 장애 후 복구 가능성 저하
- RPO/RTO 목표 미충족
- 백업 신뢰도 하락

## 3. 즉시 확인할 Dashboard

- Backup/DR dashboard: backup success, restore duration
- PostgreSQL dashboard: DB status, write error
- Infra dashboard: disk usage

## 4. Alert Rule

```yaml
annotations:
  runbook: "docs/runbooks/backup-restore-failed.md"
```

확인할 alert:

- `BackupFailed`
- `RestoreDrillFailed`
- `BackupChecksumMismatch`

## 5. 1차 확인 명령

```bash
make backup-db
make verify-backup
make restore-db
make verify-restore
```

## 6. 원인 분기표

| 관측 결과 | 판단 | 대응 |
|---|---|---|
| dump 실패 | DB 접근 또는 disk 문제 | DB/disk 상태 확인 |
| checksum 불일치 | 파일 손상 가능성 | 백업 재생성 |
| restore 실패 | dump 호환성 또는 권한 문제 | restore log 확인 |
| 정합성 SQL 실패 | 데이터 불일치 | consistency runbook 연결 |

## 7. 대응 절차

1. 실패 단계 확인
2. backup metadata와 log 확인
3. disk와 DB 상태 확인
4. 백업 재생성 또는 이전 백업 검증
5. restore DB에서 정합성 SQL 재실행

## 8. 복구 확인 기준

- backup 생성 성공
- checksum 일치
- restore DB 복원 성공
- duplicated ledger count 0
- balance mismatch count 0

## 9. 재발 방지

- backup retention과 disk alert 조정
- restore drill 주기 고정
- backup report 자동 생성

## 10. 사후 기록 템플릿

- 실패 단계:
- backup file:
- checksum result:
- restore result:
- 정합성 검증 결과:
