# Observability Evidence Plan

> 이 문서는 Ops Phase 8 Incident Runbook을 보완하기 위한 supporting document입니다.
> 별도의 추가 Ops Phase가 아닙니다.

## 1. 목적

Prometheus, Grafana, k6, Runbook은 붙이는 것만으로 운영성이 증명되지 않는다.

이 문서는 운영자가 장애를 어떻게 관측하고, 어떤 수치로 정상/비정상을 판단하고,
복구 후 어떤 결과로 정상화를 증명할 것인지 정의한다.

## 2. Ops Phase 8 Evidence Checklist

| Scenario | Required Evidence | Capture Method | Blog Usage |
| --- | --- | --- | --- |
| Redis Down / Degraded | fallback metric, related logs, recovery result, duplicate ledger count 0 | Grafana + structured logs + terminal output | Redis 장애 대응 글 |
| PostgreSQL Connection Exhausted | DB connection panel, error logs, recovery check | Grafana + DB logs + terminal output | DB 장애 대응 글 |
| Nginx 5xx Spike | 5xx panel, access log sample, upstream status | Grafana + Nginx logs | 5xx 장애 분석 글 |
| High Latency | p95/p99 latency panel, request duration histogram | Grafana + Prometheus query | 성능/운영 판단 글 |
| Failed Deployment / Rollback | blue/green status, rollback result | terminal + deployment logs | 배포 장애 대응 글 |
| Consistency Violation | violation count, duplicate prevention evidence | DB query + app logs | 금융 정합성 글 |
| Secret Leak / Security Incident | masked log evidence, checklist result | security checklist + logs | 운영 보안 글 |

실제 이미지를 이 문서에 직접 추가하지 않아도 된다.
대신 블로그나 README에 이미지를 넣기 전, 위 표의 scenario, capture method, blog usage가 맞는지 확인한다.

## 3. Placeholder Policy

실제 실행하지 않은 결과는 실제 수치처럼 기록하지 않는다.
블로그 초안에는 미확보 evidence를 실제 결과처럼 쓰지 않고, 실행 후 이미지 경로와 로그 위치를 채운다.
placeholder는 실제 evidence가 아니라 수집 계획이라는 점을 명확히 표시한다.

## Captured Evidence

| Status | Evidence | Path | Used In |
| --- | --- | --- | --- |
| Done | Ops Phase 8 Runbook Index | `docs/images/ops8-01-incident-runbook-index.png` | blog/series/12 |
| Done | Grafana Request/Latency Overview | `docs/images/ops8-02-grafana-request-latency-overview.png` | blog/series/12 |
| Done | Rollback Smoke and Consistency PASS | `docs/images/ops8-03-rollback-smoke-consistency-pass.png` | blog/series/09, blog/series/12 |

## 4. 측정 대상

운영 측면에서 남길 수치는 크게 6종류다.

| 영역 | 측정 목적 |
|---|---|
| API 성능 | RPS/TPS, p50/p95/p99, 4xx/5xx, timeout 확인 |
| 금융 정합성 | duplicate ledger, balance mismatch, invalid transition 확인 |
| Redis degraded | Redis 장애 시 fallback과 정합성 유지 확인 |
| PostgreSQL pressure | connection, rollback, lock wait, deadlock 확인 |
| Nginx 관문 | 2xx/4xx/5xx, 429, upstream latency 확인 |
| DR Drill | backup, checksum, restore, RTO/RPO, 정합성 SQL 확인 |

## 5. 측정 환경 기준

운영 측정은 실행 환경이 바뀌면 결과도 바뀐다.
따라서 수치 자체보다 같은 조건에서 다시 재현할 수 있는지가 중요하다.

모든 측정 결과에는 다음 정보를 함께 기록한다.

| 항목 | 기록 값 |
|---|---|
| 실행 일시 | TBD |
| Git commit SHA | TBD |
| 실행 브랜치 | TBD |
| OS/Architecture | TBD |
| Docker version | TBD |
| Docker Compose version | TBD |
| API worker 수 | TBD |
| PostgreSQL max connections | TBD |
| SQLAlchemy pool size | TBD |
| Redis 설정 | TBD |
| Nginx rate limit 설정 | TBD |
| k6 VUs / duration | TBD |
| 테스트 데이터 규모 | TBD |

README나 blog에 수치를 기록할 때는 다음 기준을 함께 명시한다.

```text
모든 측정은 동일한 Docker Compose 환경, 동일한 k6 시나리오,
동일한 Git commit 기준으로 수행했다.
```

## 6. 시나리오별 재현 명령과 확인 방식

측정 계획은 실제 명령으로 재현 가능해야 한다.
이미 존재하는 Makefile target은 그대로 사용하고, 아직 자동화하지 않은 항목은 `Manual check` 또는 `Planned automation`으로 표시한다.

| Scenario | 확인 방식 | 결과 파일 |
|---|---|---|
| Normal Load | `make k6-normal` | `reports/k6/normal-load-summary.json` |
| Peak Load | `make k6-peak` | `reports/k6/peak-load-summary.json` |
| Duplicate Storm | `make k6-duplicate` | `reports/k6/duplicate-storm-summary.json` |
| Redis Down / Degraded | `make ops5-demo`, `make ops7-demo` | `reports/ops/ops5-failure-recovery-drill.md`, `reports/ops/ops7-incident-timeline-postmortem.md` |
| DB Connection Exhausted | Manual check / Planned automation | `docs/34-measurement-result-template.md` |
| Nginx 5xx Spike | Manual check / Planned automation | `docs/34-measurement-result-template.md` |
| Failed Deployment / Rollback | `make ops2-demo`, `make deploy-rollback` | terminal evidence / deployment logs |
| DR Drill | `make ops4-demo` | `reports/dr/ops4-postgres-restore-drill.md` |

명령이 아직 구현되지 않은 경우에는 문서에만 성공 기준을 먼저 고정하고,
구현 Phase에서 실제 target을 추가한다.

## 7. Optional Grafana Capture Candidates

아래 목록은 프로젝트 종료 조건이 아니라, 블로그/포트폴리오를 더 보강할 때 선택적으로 수집할 수 있는 후보이다.

기본 후보:

```text
docs/images/grafana/
  01-normal-baseline-dashboard.png
  02-peak-load-dashboard.png
  03-redis-down-dashboard.png
  04-db-connection-pressure-dashboard.png
  05-nginx-rate-limit-dashboard.png
```

추가 후보:

```text
docs/images/grafana/
  06-alert-firing-consistency-violation.png
  07-alert-firing-redis-down.png
  08-prometheus-targets-up.png
  09-grafana-datasource-provisioning.png
  10-ops1-dashboard-list.png
  11-ops1-required-metrics-query.png
```

캡처는 화면 미관보다 증거성을 우선한다.

- timestamp가 보이는가?
- scenario 이름이 기록되어 있는가?
- p95/p99, 5xx, fallback, DB pressure 같은 핵심 지표가 보이는가?
- alert firing 상태가 확인되는가?

## 8. Dashboard별 필수 패널

### API Dashboard

- Request Rate
- p50/p95/p99 Latency
- 4xx/5xx Rate
- Idempotency Hit Ratio
- Redis Fallback Total
- DB Retry Total

### Infra Dashboard

- Container CPU
- Container Memory
- Container Restart Count
- OOM Events
- Disk Usage

### PostgreSQL Dashboard

- Active Connections
- Lock Wait
- Deadlock Count
- Transaction Commit/Rollback
- Slow Query Count

### Redis Dashboard

- `redis_up`
- `used_memory`
- `evicted_keys`
- `connected_clients`
- command latency

### Nginx Dashboard

- 2xx/4xx/5xx
- 429 Count
- `upstream_response_time`
- `request_time`
- denied internal endpoint access

## 9. Evidence 신뢰성 기준

각 캡처와 결과 파일에는 다음 정보 중 최소 3개 이상이 포함되어야 한다.

- 실행 일시
- scenario 이름
- Git commit SHA
- k6 scenario name
- Prometheus time range
- Grafana dashboard title
- alert name
- result file path
- 정합성 검증 결과

### Evidence 보안 검토 기준

README나 blog에 첨부하기 전 다음 값이 노출되지 않았는지 확인한다.

- 계좌번호 원문
- idempotency key 원문
- HMAC signature
- Authorization header
- DB password
- Redis password
- GitHub Actions secret
- raw request body
- 내부 IP 전체 대역이 불필요하게 노출된 화면

## 10. k6 테스트 결과 저장 기준

k6 결과는 summary JSON과 사람이 읽는 Markdown 요약을 함께 남긴다.

```text
reports/k6/
  normal-load-summary.json
  peak-load-summary.json
  duplicate-storm-summary.json
  redis-down-summary.json
  nginx-rate-limit-summary.json
```

Ops Phase 1 monitoring foundation 결과:

```text
reports/monitoring/
  ops1-prometheus-targets.md
  ops1-required-metrics.md
  ops1-grafana-provisioning.md
  ops1-compose-status.md
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

## 11. 장애 전후 비교 기준

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

## 12. Alert와 Runbook 연결 기준

Alert는 단독으로 끝나면 안 된다.
각 Alert는 severity, runbook, evidence artifact로 연결되어야 한다.

| Alert | Severity | Runbook | Evidence |
|---|---|---|---|
| RedisDown | SEV2 | `docs/runbooks/redis-down.md` | `03-redis-down-dashboard.png` |
| PostgresConnectionPressure | SEV2 | `docs/runbooks/postgres-connection-exhausted.md` | `04-db-connection-pressure-dashboard.png` |
| Nginx5xxSpike | SEV2 | `docs/runbooks/nginx-5xx-spike.md` | `reports/incidents/nginx-5xx-result.md` |
| ConsistencyViolation | SEV1 | `docs/runbooks/consistency-violation.md` | 정합성 SQL 결과 |
| SecretLeak | SEV1 | `docs/runbooks/secret-leak.md` | secret scan 결과 |
| BackupRestoreFailed | SEV2 | `docs/runbooks/backup-restore-failed.md` | DR Drill report |
| MetricsUnavailable | SEV3 | `docs/runbooks/metrics-unavailable.md` | Prometheus target 캡처 |

## 13. Reports 저장 정책

`reports/`에 모든 원본 파일을 커밋하면 repository가 빠르게 지저분해질 수 있다.
대표 결과와 재현 가능한 요약만 Git에 포함하고, raw log는 기본적으로 제외한다.

- 대표 결과 Markdown은 Git에 포함한다.
- 원본 대용량 로그는 Git에 포함하지 않는다.
- k6 summary JSON은 대표 시나리오만 포함한다.
- Grafana 캡처는 README/blog에서 사용하는 대표 이미지 위주로 포함한다.
- 민감정보가 포함될 수 있는 raw log는 커밋하지 않는다.

권장 `.gitignore` 정책:

```gitignore
reports/**/*.log
reports/**/raw/
reports/**/tmp/
*.har
*.pcap
```

포트폴리오 증거로 필요한 대표 파일은 예외 처리할 수 있다.

```gitignore
!reports/k6/*-summary.json
!reports/dr-drill/*-result.md
!reports/incidents/*-result.md
```

## 14. 정합성 검증 결과 기록 기준

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

정합성 위반은 성능 저하와 달리 허용 가능한 오차가 아니다.
1건이라도 발생하면 SEV1로 분류하고 원인 분석과 복구 검증을 먼저 수행한다.

## 15. README/blog 반영 기준

README에는 대표 결과 표와 핵심 캡처만 넣는다.

| Scenario | 핵심 관측 지표 | 결과 요약 | 정합성 |
|---|---|---|---|
| Normal Load | p95/p99, error rate | TBD | 위반 0건 |
| Redis Down | redis_up, fallback_total | degraded mode 동작 | 위반 0건 |
| DB Pressure | active_conn, p99 | DB 병목 탐지 | 위반 0건 |
| Nginx Burst | 429, upstream RPS | rate limit으로 API 보호 | 위반 0건 |
| DR Drill | restore duration, checksum | 복구 가능성 검증 | 위반 0건 |

관련 blog 글에는 상세 캡처와 수치를 넣는다.

| Blog | 추가할 캡처/수치 |
|---|---|
| 13 Infra Metrics | 정상 상태, peak load Grafana |
| 14 Nginx | rate limit 전후 비교 |
| 15 Backup/Restore | restore drill 결과 |
| 18 Internal Network | access matrix, denied access log |
| 19 Runbook | alert firing, incident report |
| 20 Failure Recovery | Redis/API/PostgreSQL recovery evidence |
| 21 Alerting | alert rule validation, CI gate |
| 22 Postmortem | incident timeline, impact evidence |

## 16. 성공 기준

- Prometheus target이 모두 UP이다.
- k6 결과 파일이 생성된다.
- Grafana 캡처에 timestamp와 scenario 이름이 포함된다.
- Redis Down 상황에서 `redis_up=0`과 fallback 증가가 관측된다.
- 모든 장애 시나리오에서 정합성 위반은 0건이다.
- DR Drill에서 checksum 검증과 restore DB 복원이 성공한다.
- Alert firing 결과가 관련 Runbook과 연결된다.

## 17. 실패 기준

- 정합성 위반이 1건 이상 발생한다.
- Grafana 캡처에 핵심 지표가 보이지 않는다.
- k6 summary JSON이 저장되지 않는다.
- Prometheus target 중 필수 target이 DOWN이다.
- DR Drill에서 restore 또는 checksum 검증이 실패한다.
- incident report가 생성되지 않는다.

## 18. Evidence Completion Checklist

이 항목은 Phase 8 Runbook 문서화 완료 기준이 아니라, 블로그/README 최종 게시 전 채워야 할 evidence checklist다.
Phase 8 완료 기준은 Incident Runbook과 supporting documents가 장애 판단·대응·복구 검증 기준을 제공하는지 여부로 본다.

- [ ] 선택 Grafana 캡처 후보 중 게시에 필요한 대표 이미지 저장
- [ ] Prometheus target UP 캡처 저장
- [ ] k6 summary JSON 저장
- [ ] DR Drill 결과 Markdown/JSON 저장
- [ ] Redis down, DB pressure, Nginx burst 전후 비교 표 작성
- [ ] 정합성 검증 결과 0건 기록
- [ ] README에는 요약 표와 대표 캡처만 반영
- [ ] blog에는 상세 수치와 트러블슈팅을 반영
