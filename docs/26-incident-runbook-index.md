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
