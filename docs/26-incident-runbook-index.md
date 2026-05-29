# Incident Runbook Index

## 1. 목적

모니터링은 장애를 감지하는 장치이고, Runbook은 장애가 났을 때 운영자가 어떤 순서로 판단할지 고정하는 문서다. Phase 18에서는 주요 장애를 Runbook으로 분리해 탐지 지표, 확인 명령, 1차 대응, 복구 기준, 재발 방지를 정리한다.

## 2. Runbook 목록

| 장애 | 문서 |
|---|---|
| Redis Down | [runbooks/redis-down.md](runbooks/redis-down.md) |
| PostgreSQL Connection Exhausted | [runbooks/postgres-connection-exhausted.md](runbooks/postgres-connection-exhausted.md) |
| Nginx 5xx Spike | [runbooks/nginx-5xx-spike.md](runbooks/nginx-5xx-spike.md) |
| High Latency p99 | [runbooks/high-latency-p99.md](runbooks/high-latency-p99.md) |
| Disk Full | [runbooks/disk-full.md](runbooks/disk-full.md) |
| Failed Deployment | [runbooks/failed-deployment.md](runbooks/failed-deployment.md) |

## 3. 공통 형식

각 Runbook은 다음 형식을 따른다.

1. 증상
2. 사용자 영향
3. 즉시 확인할 지표
4. 확인 명령
5. 1차 대응
6. 복구 확인 기준
7. 재발 방지
8. 사후 기록 템플릿

## 4. README 요약 문장

장애 대응 능력을 코드 구현만으로 설명하기 어렵다고 판단해, Redis 장애, DB 커넥션 고갈, Nginx 5xx 증가, p99 지연, 디스크 부족, 배포 실패에 대한 Runbook을 작성한다. 각 Runbook은 탐지 지표, 확인 명령, 1차 대응, 복구 기준, 재발 방지 항목으로 구성한다.
