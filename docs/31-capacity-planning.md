# Capacity Planning

> 이 문서는 현재 필수 Ops Phase에 포함되지 않는 optional enhancement 문서입니다.
> 프로젝트 종료 기준에는 포함하지 않고, 향후 운영 고도화 시 참고합니다.

## 1. 목적

운영자는 현재 구성으로 어느 정도 트래픽을 처리할 수 있는지, 어떤 지표가 어느 수준에 도달하면 확장해야 하는지 알아야 한다.

이 문서는 API, DB, Redis, Nginx, container resource의 초기 capacity planning 기준을 정리한다.

## 2. 조정 기준

| 항목 | 초기값 | 관측 기준 | 조정 기준 |
|---|---|---|---|
| API replicas | 1~2 | p95/p99, CPU | p95 지속 상승 |
| DB pool size | 5~10 | pool wait, active conn | connection pressure |
| Redis pool | 10 | timeout/fallback | Redis latency |
| Nginx rate limit | 20r/s | 429 비율 | 정상 요청 차단 시 완화 |
| Postgres max_conn | 100 | active conn | 80% 초과 시 경고 |
| Container CPU | 1~2 cores | throttling | throttling 지속 |
| Container Memory | 512Mi~1Gi | OOM, usage | OOM event 발생 |

## 3. 목표 TPS/RPS

초기 로컬 기준:

- smoke: 정상 API 흐름 확인
- normal load: 지속 요청 처리 확인
- peak load: p95/p99와 DB/Redis/Nginx 병목 확인
- duplicate storm: 중복 반영 0건 확인

## 4. 확장 판단

- API CPU가 높고 DB wait가 낮으면 API replica/worker 조정
- DB connection pressure가 높으면 pool size와 query/transaction 점검
- Redis fallback이 급증하면 Redis latency와 availability 확인
- Nginx 429가 정상 요청을 과도하게 차단하면 rate limit 조정
- disk 사용률이 85%를 넘으면 backup/log retention 점검

## 5. 완료 기준

- k6 peak 결과와 infra metric을 함께 기록한다.
- p95/p99 상승 시 어느 계층을 먼저 볼지 문서화한다.
- DB pool, Redis pool, Nginx rate limit 조정 기준을 README에 남긴다.
