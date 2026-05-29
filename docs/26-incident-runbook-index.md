# Ops Phase 7 - Incident Runbook & On-call Simulation

## 1. 해결하려는 운영 문제

모니터링은 장애를 감지하는 장치이고, Runbook은 장애가 났을 때 운영자가 어떤 순서로 판단할지 고정하는 문서다.

Ops Phase 7은 Redis 장애, DB connection 고갈, Nginx 5xx, p99 latency, disk full, failed deployment 상황을 재현 가능한 runbook으로 정리한다.

## 2. 구현 범위

- 장애별 runbook 작성
- alert rule과 runbook 링크 연결
- 장애 훈련 명령 설계
- 복구 후 정합성 검증 기준 정리
- incident report 결과 파일 설계

## 3. 제외 범위

- 실제 on-call rotation 시스템 구축은 제외한다.
- PagerDuty, Opsgenie 같은 외부 incident tool 연동은 제외한다.
- 장애 자동 복구는 초기 범위에서 제외한다.
- 운영 DB destructive drill은 제외한다.

## 4. 파일/디렉터리 변경 계획

```text
docs/
  runbooks/
    redis-down.md
    postgres-connection-exhausted.md
    nginx-5xx-spike.md
    high-latency-p99.md
    disk-full.md
    failed-deployment.md
    consistency-violation.md
    secret-leak.md
    backup-restore-failed.md
    metrics-unavailable.md

reports/
  incidents/
    redis-down/
      result.md
    failed-deployment/
      result.md
```

## 5. 검증 명령어

```bash
make drill-redis-down
make drill-postgres-connection-exhausted
make drill-nginx-5xx
make drill-high-latency
make drill-disk-full
make drill-failed-deployment
make drill-consistency-violation
make drill-secret-leak
```

성공 기준:

- 각 장애별 재현 명령 존재
- 장애 재현 후 alert firing 확인
- runbook 절차대로 복구 가능
- 복구 후 정합성 검증 통과
- `reports/incidents/{scenario}/result.md` 생성

## 6. 완료 기준과 README에 남길 결과

### Runbook 목록

| 장애 | 문서 |
|---|---|
| Redis Down | [runbooks/redis-down.md](runbooks/redis-down.md) |
| PostgreSQL Connection Exhausted | [runbooks/postgres-connection-exhausted.md](runbooks/postgres-connection-exhausted.md) |
| Nginx 5xx Spike | [runbooks/nginx-5xx-spike.md](runbooks/nginx-5xx-spike.md) |
| High Latency p99 | [runbooks/high-latency-p99.md](runbooks/high-latency-p99.md) |
| Disk Full | [runbooks/disk-full.md](runbooks/disk-full.md) |
| Failed Deployment | [runbooks/failed-deployment.md](runbooks/failed-deployment.md) |
| Consistency Violation | [runbooks/consistency-violation.md](runbooks/consistency-violation.md) |
| Secret Leak | [runbooks/secret-leak.md](runbooks/secret-leak.md) |
| Backup Restore Failed | [runbooks/backup-restore-failed.md](runbooks/backup-restore-failed.md) |
| Metrics Unavailable | [runbooks/metrics-unavailable.md](runbooks/metrics-unavailable.md) |

### 공통 템플릿

각 runbook은 아래 구조를 따른다.

1. 장애 정의
2. 사용자 영향
3. 즉시 확인할 Dashboard
4. Alert Rule
5. 1차 확인 명령
6. 원인 분기표
7. 대응 절차
8. 복구 확인 기준
9. 재발 방지
10. 사후 기록 템플릿

### Alert Rule 연결

각 Alert Rule에는 반드시 runbook 링크를 추가한다.

```yaml
annotations:
  runbook: "docs/runbooks/redis-down.md"
```

### Severity Level

| Severity | 기준 | 예시 |
|---|---|---|
| SEV1 | 금융 정합성 위반 또는 핵심 거래 처리 불가 | ledger 중복 반영, PostgreSQL down, secret leak |
| SEV2 | degraded mode 지속 또는 사용자 요청 실패 증가 | Redis down, Nginx 5xx spike, p99 급증 |
| SEV3 | 예방 대응 가능한 운영 위험 | disk 85%, backup 지연, dashboard 일부 누락 |
| SEV4 | 비긴급 개선 항목 | 문서 보완, alert threshold 조정 |

정합성 위반은 성능 저하와 다르게 error budget을 두지 않는다.
1건 발생 시 SEV1 incident로 분류한다.

### Incident Lifecycle

Runbook은 다음 lifecycle을 기준으로 작성한다.

1. Preparation
   - dashboard, alert, runbook, backup 준비
2. Detection & Analysis
   - alert firing, dashboard 확인, 영향 범위 판단
3. Containment
   - rate limit 강화, traffic rollback, admin endpoint 제한, degraded mode 유지
4. Eradication & Recovery
   - 원인 제거, 서비스 복구, 정합성 검증
5. Post-Incident Activity
   - incident report, 재발 방지 action item, threshold/runbook 수정
