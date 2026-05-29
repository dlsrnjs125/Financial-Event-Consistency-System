# Observability Evidence Plan

## 1. 목적

Prometheus, Grafana, k6, Runbook은 붙이는 것만으로 운영성이 증명되지 않는다.

이 문서는 운영자가 장애를 어떻게 관측하고, 어떤 수치로 정상/비정상을 판단하고,
복구 후 어떤 결과로 정상화를 증명할 것인지 정의한다.

## 2. 측정 대상

운영 측면에서 남길 수치는 크게 6종류다.

| 영역 | 측정 목적 |
|---|---|
| API 성능 | RPS/TPS, p50/p95/p99, 4xx/5xx, timeout 확인 |
| 금융 정합성 | duplicate ledger, balance mismatch, invalid transition 확인 |
| Redis degraded | Redis 장애 시 fallback과 정합성 유지 확인 |
| PostgreSQL pressure | connection, rollback, lock wait, deadlock 확인 |
| Nginx 관문 | 2xx/4xx/5xx, 429, upstream latency 확인 |
| DR Drill | backup, checksum, restore, RTO/RPO, 정합성 SQL 확인 |

## 3. 필수 Grafana 캡처

필수 캡처:

```text
docs/images/grafana/
  01-normal-baseline-dashboard.png
  02-peak-load-dashboard.png
  03-redis-down-dashboard.png
  04-db-connection-pressure-dashboard.png
  05-nginx-rate-limit-dashboard.png
```

추가 캡처:

```text
docs/images/grafana/
  06-alert-firing-consistency-violation.png
  07-alert-firing-redis-down.png
  08-prometheus-targets-up.png
  09-dashboard-provisioning.png
```

캡처는 화면 미관보다 증거성을 우선한다.

- timestamp가 보이는가?
- scenario 이름이 기록되어 있는가?
- p95/p99, 5xx, fallback, DB pressure 같은 핵심 지표가 보이는가?
- alert firing 상태가 확인되는가?

## 4. k6 테스트 결과 저장 기준

k6 결과는 summary JSON과 사람이 읽는 Markdown 요약을 함께 남긴다.

```text
reports/k6/
  normal-load-summary.json
  peak-load-summary.json
  duplicate-storm-summary.json
  redis-down-summary.json
  nginx-rate-limit-summary.json
```

기록할 API 성능 수치:

| 지표 | 의미 | 기록 위치 |
|---|---|---|
| RPS/TPS | 초당 요청/거래 처리량 | k6 summary, Grafana |
| p50 | 일반 응답시간 | k6 summary |
| p95 | 느린 5% 요청 | k6 summary, Grafana |
| p99 | 가장 느린 1% 요청 | k6 summary, Grafana |
| 4xx rate | 인증/검증 실패 또는 rate limit | Grafana |
| 5xx rate | 서버 오류 | Grafana |
| timeout count | timeout 발생 | k6 summary |

README에는 평균 응답시간보다 p95/p99를 중심으로 기록한다.

## 5. 장애 전후 비교 기준

### 성능/장애 비교

| Scenario | RPS | p50 | p95 | p99 | 5xx Rate | 정합성 위반 |
|---|---:|---:|---:|---:|---:|---:|
| Normal Load | TBD | TBD | TBD | TBD | TBD | 0 |
| Peak Load | TBD | TBD | TBD | TBD | TBD | 0 |
| Duplicate Storm | TBD | TBD | TBD | TBD | TBD | 0 |
| Redis Down | TBD | TBD | TBD | TBD | TBD | 0 |
| DB Pressure | TBD | TBD | TBD | TBD | TBD | 0 |
| Nginx Burst | TBD | TBD | TBD | TBD | TBD | 0 |

구현 후 `TBD`는 실제 측정값으로 대체한다.

### Redis Normal vs Redis Down

| Metric | Normal | Redis Down | 해석 |
|---|---:|---:|---|
| redis_up | TBD | 0 | Redis 장애 탐지 |
| redis_fallback_total | TBD | 증가 | DB fallback 동작 |
| API p95 | TBD | TBD | degraded mode 지연 증가 |
| API p99 | TBD | TBD | tail latency 확인 |
| DB retry count | TBD | TBD | DB 부하 전이 확인 |
| Duplicate ledger count | 0 | 0 | 최종 정합성 유지 |

Redis 장애 상황에서는 `redis_up=0`으로 전환되고 fallback_total이 증가해야 한다.
p95/p99 응답시간은 상승할 수 있지만 PostgreSQL transaction과 unique constraint 기준으로 ledger 중복 반영은 0건이어야 한다.

### Rate Limit 전후

| Metric | Rate Limit Off | Rate Limit On | 해석 |
|---|---:|---:|---|
| Incoming RPS | TBD | TBD | 동일 burst 부하 |
| Upstream forwarded RPS | TBD | TBD | API 보호 여부 |
| 429 count | 0 | TBD | 제한 동작 확인 |
| API CPU | TBD | TBD | upstream 부하 완화 |
| API p99 | TBD | TBD | tail latency 완화 여부 |
| 5xx rate | TBD | TBD | 장애 확산 방지 |

금융 이벤트 POST 요청은 Nginx 자동 retry를 조심해야 한다.
POST retry가 중복 이벤트를 늘릴 수 있으므로, 자동 재시도는 제한하고 idempotency key와 DB unique constraint로 최종 방어한다.

### Backup Only vs Restore Drill

| 항목 | Backup Only | Restore Drill |
|---|---:|---:|
| 백업 파일 생성 | O | O |
| checksum 검증 | X | O |
| restore DB 복원 | X | O |
| 정합성 SQL 실행 | X | O |
| RTO 측정 | X | O |
| 복구 가능성 검증 | 낮음 | 높음 |

## 6. 정합성 검증 결과 기록 기준

정합성 검증 결과는 항상 0건을 목표로 기록한다.

| 지표 | 목표 |
|---|---:|
| duplicate ledger count | 0 |
| account balance mismatch | 0 |
| invalid state transition | 0 |
| orphan idempotency record | 0 |
| terminal status 이후 변경 시도 | 0 |

README 요약 예시:

```text
정합성 검증 결과
- Duplicate ledger entries: 0
- Account balance mismatch: 0
- Invalid state transition: 0
- Orphan idempotency records: 0
```

## 7. README/blog 반영 기준

README에는 대표 결과 표와 핵심 캡처만 넣는다.

| Scenario | 핵심 관측 지표 | 결과 요약 | 정합성 |
|---|---|---|---|
| Normal Load | p95/p99, error rate | TBD | 위반 0건 |
| Redis Down | redis_up, fallback_total | degraded mode 동작 | 위반 0건 |
| DB Pressure | active_conn, p99 | DB 병목 탐지 | 위반 0건 |
| Nginx Burst | 429, upstream RPS | rate limit으로 API 보호 | 위반 0건 |
| DR Drill | restore duration, checksum | 복구 가능성 검증 | 위반 0건 |

blog 13~19에는 상세 캡처와 수치를 넣는다.

| Blog | 추가할 캡처/수치 |
|---|---|
| 13 Infra Metrics | 정상 상태, peak load Grafana |
| 14 Nginx | rate limit 전후 비교 |
| 15 Backup/Restore | restore drill 결과 |
| 16 Ansible | playbook 실행 결과, idempotency log |
| 17 PowerShell | incident snapshot JSON |
| 18 Internal Network | access matrix, denied access log |
| 19 Runbook | alert firing, incident report |

## 8. 완료 기준

- 필수 Grafana 캡처 5개 이상 저장
- Prometheus target UP 캡처 저장
- k6 summary JSON 저장
- DR Drill 결과 Markdown/JSON 저장
- Redis down, DB pressure, Nginx burst 전후 비교 표 작성
- 정합성 검증 결과 0건 기록
- README에는 요약 표와 대표 캡처만 반영
- blog에는 상세 수치와 트러블슈팅을 반영
