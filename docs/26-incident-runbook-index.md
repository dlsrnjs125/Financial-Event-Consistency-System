# Ops Phase 8 - Incident Runbook Finalization

> 이 문서는 Ops Phase 8의 핵심 산출물이다.
> Ops Phase 8은 본 프로젝트의 마지막 필수 Ops 단계이며, 장애 탐지·대응·복구 검증·재발 방지 절차를 정리한다.

## 1. 해결하려는 운영 문제

모니터링은 장애를 감지하는 장치이고, Runbook은 장애가 났을 때 운영자가 어떤 순서로 판단할지 고정하는 문서다.

Ops Phase 8은 Redis 장애, DB connection 고갈, Nginx 5xx, p99 latency, failed deployment, consistency violation, security incident 상황을 운영자가 추적 가능한 runbook으로 정리한다.
새 장애 주입 기능을 늘리는 단계가 아니라, Ops Phase 4~7에서 만든 DR Drill, Failure Recovery Drill, Alert Rule, Postmortem evidence를 한 곳에서 찾을 수 있게 연결하는 문서화 단계다.

## 2. 구현 범위

- 장애별 runbook 작성
- alert rule과 runbook 링크 연결
- 장애 훈련 명령, local evidence, manual checklist 연결
- 복구 후 정합성 검증 기준 정리
- incident report 결과 파일 설계
- SLO/SLI, observability evidence, measurement result template 연결

## 3. 제외 범위

- 실제 on-call rotation 시스템 구축은 제외한다.
- PagerDuty, Opsgenie 같은 외부 incident tool 연동은 제외한다.
- 장애 자동 복구는 초기 범위에서 제외한다.
- 운영 DB destructive drill은 제외한다.

## 4. Ops Phase 8 Completion Criteria

Ops Phase 8은 Incident Runbook을 완성하고, 장애 대응 기준을 문서화하는 단계다.

완료 기준:

- 필수 장애 시나리오별 Runbook이 존재한다.
- 각 Runbook은 장애 상황, 예상 원인, 사용자 영향, 탐지 방법, 대응 방법, 복구 검증, 재발 방지, README/블로그 기록 문장을 포함한다.
- 각 Runbook은 관련 SLO/SLI와 연결된다.
- 각 Runbook은 수집해야 할 관측 증거와 연결된다.
- 실제 존재하는 명령과 수동 확인 항목이 구분되어 있다.
- 실제 측정하지 않은 결과는 placeholder 또는 TODO로 표시되어 있다.
- Ops Extension Track은 Phase 8에서 종료된다.

## 5. Supporting Documents 연결

| Supporting document | Runbook에서 사용하는 역할 |
| --- | --- |
| [29-slo-sli-error-budget.md](29-slo-sli-error-budget.md) | 장애 심각도, SLO 위반, error budget 판단 기준 |
| [33-observability-evidence-plan.md](33-observability-evidence-plan.md) | Prometheus/Grafana/log screenshot evidence 수집 기준 |
| [34-measurement-result-template.md](34-measurement-result-template.md) | 장애 대응 결과와 측정값 기록 양식 |
| [27-threat-model.md](27-threat-model.md) | 보안성 장애 시나리오의 위협 근거 |
| [32-security-checklist.md](32-security-checklist.md) | 운영 보안 점검 기준 |

## 6. 파일/디렉터리 기준

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

## 7. 검증 기준

| Scenario | Verification mode | Evidence |
| --- | --- | --- |
| Redis Down / Redis Degraded | Local command | `make ops5-demo`, `make ops7-demo` |
| PostgreSQL connection exhausted | Manual checklist / planned verification | readiness failure, DB connection metric, recovery checklist |
| Nginx 5xx spike | Manual checklist / planned verification | Nginx access log, HTTP 5xx metric, routed smoke |
| High latency / p99 latency spike | Local report / manual checklist | k6 result, latency dashboard, p95/p99 metric |
| Failed deployment / rollback | Local command | `make ops2-demo`, `make deploy-rollback` |
| Consistency violation | Local consistency check | duplicate ledger count, idempotency violation count, reconciliation failure metric |
| Secret leak or security incident | Manual checklist | Threat Model, Secret Management Policy, Security Checklist |

### 실제 존재하는 검증 명령

아래 명령은 현재 Makefile에 존재하는 명령만 기록한다.
자동화되지 않은 항목은 code block에 넣지 않고 Manual verification 또는 Planned automation으로 분리한다.

```bash
make ops2-demo
make ops4-demo
make ops5-demo
make ops6-demo
make ops7-demo
make deploy-status
make deploy-smoke
make deploy-rollback
make deploy-verify
make k6-normal
make k6-peak
make k6-duplicate
make k6-verify
make security-log-check
```

Manual verification:

- Grafana dashboard에서 p95/p99 latency, 5xx, Redis fallback, DB connection panel을 확인한다.
- structured log에서 `trace_id`, `request_id`, `event_id`, `error_code` 기준으로 장애 요청을 추적한다.
- PostgreSQL connection exhaustion은 DB exporter panel, PostgreSQL log, `/ready` failure를 기준으로 확인한다.
- Secret Leak / Security Incident는 Threat Model, Secret Management Policy, Security Checklist와 `make security-log-check` 결과를 함께 확인한다.

Planned automation:

- `make ops8-incident-drill`은 현재 존재하지 않는다. 필요하면 후속 고도화에서 추가한다.
- DB connection exhaustion, Nginx 5xx spike, Secret leak drill은 현재 Runbook/manual checklist 기준으로 관리한다.

성공 기준:

- 각 장애별 local evidence 또는 manual checklist 존재
- 장애 재현 또는 planned verification 기준 명시
- alert firing 또는 detection metric 확인 기준 명시
- runbook 절차대로 복구 가능
- 복구 후 정합성 검증 통과
- incident report 또는 measurement result template으로 결과 기록 가능

## 8. 완료 기준과 README에 남길 결과

### Runbook 목록

| 장애 | 문서 |
|---|---|
| Redis Down | [runbooks/redis-down.md](runbooks/redis-down.md) |
| Redis Degraded | [23-failure-recovery-runbook-drill.md](23-failure-recovery-runbook-drill.md), [25-incident-timeline-postmortem-drill.md](25-incident-timeline-postmortem-drill.md) |
| PostgreSQL Connection Exhausted | [runbooks/postgres-connection-exhausted.md](runbooks/postgres-connection-exhausted.md) |
| Nginx 5xx Spike | [runbooks/nginx-5xx-spike.md](runbooks/nginx-5xx-spike.md) |
| High Latency p99 | [runbooks/high-latency-p99.md](runbooks/high-latency-p99.md) |
| Disk Full | [runbooks/disk-full.md](runbooks/disk-full.md) |
| Failed Deployment | [runbooks/failed-deployment.md](runbooks/failed-deployment.md) |
| Consistency Violation | [runbooks/consistency-violation.md](runbooks/consistency-violation.md) |
| Secret Leak | [runbooks/secret-leak.md](runbooks/secret-leak.md) |
| Backup Restore Failed | [runbooks/backup-restore-failed.md](runbooks/backup-restore-failed.md) |
| Metrics Unavailable | [runbooks/metrics-unavailable.md](runbooks/metrics-unavailable.md) |

## Scenario 1. Redis Down / Redis Degraded

#### 장애 상황
- Redis lock/cache 계층이 down 또는 degraded 상태가 되어 `/ready`에서 Redis dependency가 degraded로 표시된다.
- PostgreSQL은 Source of Truth로 유지되며, 핵심 판단 기준은 duplicate ledger와 idempotency violation이 0건인지 여부다.

#### 예상 원인
- Redis container stop/restart, network timeout, Redis exporter scrape 실패
- Redis connection pool 고갈 또는 command latency 증가
- lock/cache operation timeout으로 fallback 증가

#### 사용자 영향
- duplicate request 처리 latency가 증가할 수 있다.
- PostgreSQL이 정상이라면 금융 이벤트의 최종 정합성은 유지되어야 한다.
- Redis 장애가 길어지면 API p95/p99와 DB retry가 증가할 수 있다.

#### 탐지 방법
- `/ready`에서 `redis=degraded` 또는 dependency degraded 확인
- Prometheus: `financial_readiness_dependency_status{dependency="redis"}`, `financial_redis_operation_failed_total`, `financial_redis_fallback_total`
- Redis exporter 사용 시 `redis_up` 또는 `up{job="redis-exporter"}` 확인
- Local evidence: `make ops5-demo`, `make ops7-demo`

#### 대응 방법
- 1단계: `/health`, `/ready`로 API와 PostgreSQL 정상 여부를 먼저 확인한다.
- 2단계: Redis fallback metric과 API p95/p99 상승 여부를 확인한다.
- 3단계: duplicate smoke 결과가 200/202 계열로 처리되는지 확인한다.
- 4단계: Redis container 또는 Redis service를 재시작한다.
- 5단계: duplicate ledger count와 idempotency violation count가 0인지 확인한다.

#### 복구 검증
- `/ready`가 정상 또는 Redis recovered 상태로 돌아온다.
- `make ops5-demo` 또는 `make ops7-demo` report에서 duplicate ledger count 0, idempotency violation count 0을 확인한다.
- Redis fallback 증가가 멈추고 API p95/p99가 baseline에 가까워진다.

#### 재발 방지
- Redis timeout/backoff 기준과 fallback alert threshold를 조정한다.
- Redis degraded dashboard panel과 alert annotation을 보강한다.
- Redis 장애 시 PostgreSQL 부하 전이를 관측하는 panel을 추가한다.

#### README/블로그 기록 문장
- Redis 장애는 성능 저하로 이어질 수 있지만, PostgreSQL 기준 duplicate ledger 0건과 idempotency violation 0건을 복구 검증 기준으로 삼았다.

## Scenario 2. PostgreSQL Connection Exhausted

#### 장애 상황
- PostgreSQL connection pool 또는 DB connection이 고갈되어 transaction 처리와 readiness가 실패한다.
- PostgreSQL은 최종 Source of Truth이므로 Redis degraded와 달리 critical incident로 분류한다.

#### 예상 원인
- SQLAlchemy pool size 부족, long-running transaction, lock wait 증가
- 트래픽 spike로 인한 active connection 급증
- DB restart, network partition, slow query 누적

#### 사용자 영향
- 거래 이벤트 처리 실패, `/ready` 실패, API 5xx/503 증가가 발생할 수 있다.
- 정합성 검증 전까지 복구 완료를 선언하지 않는다.

#### 탐지 방법
- `/ready` 실패와 `financial_readiness_dependency_status{dependency="postgres"}` 확인
- Prometheus/Grafana: DB active connection, lock wait, rollback, API 5xx/p99
- PostgreSQL logs에서 connection refused, too many clients, lock wait message 확인
- Manual check: PostgreSQL exporter panel 또는 `pg_stat_activity` 확인

#### 대응 방법
- 1단계: API down인지 DB connection exhausted인지 `/health`와 `/ready`로 분리한다.
- 2단계: active connection, long transaction, lock wait query를 확인한다.
- 3단계: 불필요한 batch나 과도한 traffic을 일시 중지한다.
- 4단계: connection pool 설정과 DB max connection 기준을 검토한다.
- 5단계: 복구 후 consistency SQL 또는 `make deploy-verify` 계열 검증을 실행한다.

#### 복구 검증
- `/ready`가 PASS로 돌아온다.
- API smoke request가 성공한다.
- duplicate ledger, account balance mismatch, orphan ledger, idempotency violation count가 0이다.

#### 재발 방지
- pool size, max overflow, timeout, slow query threshold를 재조정한다.
- connection usage warning/critical alert를 추가한다.
- long transaction dashboard와 runbook query를 보강한다.

#### README/블로그 기록 문장
- PostgreSQL connection 고갈은 Source of Truth 접근 실패로 보고, readiness 복구와 정합성 SQL PASS를 함께 복구 기준으로 둔다.

## Scenario 3. Nginx 5xx Spike

#### 장애 상황
- Nginx public/internal gateway에서 5xx가 증가해 사용자 요청 실패가 늘어난다.
- upstream API 장애, Blue-Green routing 오류, readiness 실패, rate limit/timeout 설정 오류를 구분해야 한다.

#### 예상 원인
- active upstream이 잘못된 container를 가리킴
- API container unhealthy 또는 restart 중
- Nginx config reload 실패, upstream timeout, connection refused
- 배포 직후 Green 검증 누락 또는 rollback 지연

#### 사용자 영향
- 외부 금융사 이벤트 요청이 실패하거나 retry가 증가한다.
- POST retry가 중복 이벤트를 늘릴 수 있으므로 idempotency/unique constraint 검증이 필요하다.

#### 탐지 방법
- Prometheus: `financial_http_requests_total` 또는 Nginx 5xx panel
- Nginx access/error log의 upstream status, request time, upstream response time
- `make deploy-status`, `make deploy-smoke`로 active upstream과 smoke 확인
- Manual check: Nginx config test와 upstream health 확인

#### 대응 방법
- 1단계: 5xx가 public endpoint인지 internal endpoint인지 분리한다.
- 2단계: active upstream, API `/health`, API `/ready`를 확인한다.
- 3단계: 배포 직후라면 Green 상태와 routed smoke를 확인한다.
- 4단계: 이상이 있으면 traffic rollback을 수행한다.
- 5단계: rollback 후 duplicate/event/ledger consistency를 검증한다.

#### 복구 검증
- `make deploy-smoke` 또는 routed smoke request가 성공한다.
- Nginx 5xx rate가 baseline으로 돌아온다.
- `make deploy-verify` 또는 consistency SQL이 PASS다.

#### 재발 방지
- 배포 전 Green readiness gate를 강화한다.
- upstream 전환 전후 smoke와 rollback checklist를 보강한다.
- Nginx 5xx alert에 active upstream과 rollback runbook 링크를 포함한다.

#### README/블로그 기록 문장
- Nginx 5xx spike는 단순 gateway 오류가 아니라 배포 routing, API readiness, POST retry 정합성까지 함께 확인하는 incident로 정리했다.

## Scenario 4. High Latency / p95, p99 Latency Spike

#### 장애 상황
- 평균 응답은 정상처럼 보여도 p95/p99 latency가 상승해 timeout과 retry 가능성이 커진다.
- 금융 이벤트에서는 tail latency가 retry storm과 duplicate request로 이어질 수 있다.

#### 예상 원인
- Redis fallback 증가, DB lock wait, slow query, container CPU throttling
- Nginx upstream latency 증가, connection pool wait
- duplicate storm 또는 external partner retry 증가

#### 사용자 영향
- 일부 요청이 timeout되고 외부 시스템 retry가 증가할 수 있다.
- 중복 요청이 늘어나며 idempotency와 DB unique constraint 방어가 더 중요해진다.

#### 탐지 방법
- Prometheus: `financial_http_request_duration_seconds`, `financial_transaction_processing_duration_seconds`
- Grafana p95/p99 latency panel과 request rate panel
- Redis fallback, DB transaction duration, Nginx upstream latency 동시 확인
- Local evidence: k6 result와 Grafana capture

#### 대응 방법
- 1단계: p95/p99 spike가 전체 API인지 transaction endpoint인지 분리한다.
- 2단계: Redis fallback, DB lock wait, Nginx upstream latency를 순서대로 확인한다.
- 3단계: duplicate storm이면 rate limit과 idempotency conflict 상태를 확인한다.
- 4단계: 병목 dependency를 완화하거나 traffic rollback/rate limit 조정을 수행한다.
- 5단계: latency 복구 후 정합성 count-only 검증을 수행한다.

#### 복구 검증
- p95/p99가 SLO 기준 안으로 돌아온다.
- 5xx와 timeout이 baseline으로 돌아온다.
- duplicate ledger count와 invalid state transition count가 0이다.

#### 재발 방지
- p95/p99 alert threshold를 SLO 문서와 맞춘다.
- slow query, Redis fallback, upstream latency panel을 같은 dashboard에 배치한다.
- timeout/retry/backoff 정책을 재검토한다.

#### README/블로그 기록 문장
- High latency incident는 평균 응답시간이 아니라 p95/p99와 retry/duplicate 영향까지 함께 보는 runbook으로 정리했다.

## Scenario 5. Failed Deployment / Rollback

#### 장애 상황
- Green 배포 검증 실패 또는 전환 후 오류로 active upstream rollback이 필요하다.
- DB rollback은 자동화하지 않고, API traffic rollback을 기본 대응으로 둔다.

#### 예상 원인
- Green API readiness 실패, migration 호환성 문제, Nginx upstream 설정 오류
- 배포 이미지 오류, 환경 변수 누락, smoke test 실패
- 배포 후 API 5xx 또는 consistency check 실패

#### 사용자 영향
- 전환 전 실패는 사용자 영향 없이 차단되어야 한다.
- 전환 후 실패는 요청 실패와 retry 증가로 이어질 수 있다.

#### 탐지 방법
- `make deploy-status`, `make deploy-smoke`, `make deploy-verify`
- Nginx active upstream, API `/health`, `/ready`
- CI/CD Deployment Gate Summary와 Ops2 evidence

#### 대응 방법
- 1단계: 현재 active upstream이 Blue인지 Green인지 확인한다.
- 2단계: Green `/health`, `/ready`, smoke 결과를 확인한다.
- 3단계: 전환 후 장애라면 `make deploy-rollback`으로 Blue traffic rollback을 수행한다.
- 4단계: rollback 후 routed smoke와 consistency verification을 실행한다.
- 5단계: 실패 원인을 deployment note와 incident report에 남긴다.

#### 복구 검증
- active upstream이 정상 환경으로 돌아온다.
- `/health`, `/ready`, smoke request가 PASS다.
- `make deploy-verify` 또는 consistency SQL이 PASS다.

#### 재발 방지
- Green preflight gate와 rollback checklist를 강화한다.
- backward-compatible migration 원칙을 문서화한다.
- deployment failure alert와 change management 문서를 연결한다.

#### README/블로그 기록 문장
- Failed deployment는 DB rollback이 아니라 traffic rollback으로 완화하고, smoke와 consistency check를 통과해야 복구로 판단한다.

## Scenario 6. Consistency Violation

#### 장애 상황
- duplicate ledger, account balance mismatch, invalid transition, idempotency violation 같은 금융 정합성 위반이 발생한다.
- availability 장애보다 더 높은 우선순위의 SEV1 incident로 본다.

#### 예상 원인
- transaction boundary 누락, unique constraint 우회, retry/read-after-conflict 결함
- 잘못된 상태 전이 허용, ledger/account update 불일치
- 수동 DB 조작 또는 migration 부작용

#### 사용자 영향
- 잔액 불일치, 중복 반영, 취소/정산 상태 오류로 이어질 수 있다.
- 복구 전까지 관련 이벤트 재처리나 자동 보정은 중지해야 한다.

#### 탐지 방법
- Prometheus: `financial_reconciliation_failures_total`, `financial_invalid_state_transition_total`
- consistency SQL: duplicate ledger count, account balance mismatch, orphan ledger, duplicated idempotency key
- Reports: Ops4/5/7 count-only evidence
- Logs: trace_id/request_id/event_id 기준 원인 추적

#### 대응 방법
- 1단계: 영향 받은 event/account 범위를 count-only로 확인한다.
- 2단계: 신규 처리 확산을 막기 위해 관련 traffic 또는 batch를 일시 중지한다.
- 3단계: 원인 transaction path와 최근 배포/migration을 확인한다.
- 4단계: 보정이 필요하면 수동 SQL이 아니라 검토된 compensating transaction 절차를 따른다.
- 5단계: 재처리 후 consistency SQL을 다시 실행한다.

#### 복구 검증
- duplicate ledger count 0, account balance mismatch 0, invalid transition 0, idempotency violation 0이다.
- reconciliation failure가 최근 window에서 재발하지 않는다.
- incident report에 원인, 영향 범위, 보정 방식, 재발 방지 항목이 남는다.

#### 재발 방지
- regression test와 CI consistency gate를 추가하거나 강화한다.
- DB constraint, transaction boundary, state machine validation을 재검토한다.
- reconciliation alert와 postmortem checklist를 보강한다.

#### README/블로그 기록 문장
- 정합성 위반은 error budget을 두지 않고 1건이라도 SEV1로 분류하며, count-only SQL과 postmortem으로 복구를 검증한다.

## Scenario 7. Secret Leak / Security Incident

#### 장애 상황
- HMAC secret, client secret, token, raw account_no, idempotency key 원문이 로그/report/screenshot에 노출되었거나 노출이 의심된다.
- 이벤트 위조, replay attack, 내부 endpoint 노출로 이어질 수 있는 security incident다.

#### 예상 원인
- debug logging, raw request/response 저장, screenshot 마스킹 누락
- GitHub secret 또는 `.env` 파일 노출
- public endpoint에 `/metrics`, `/ready`, `/admin/*`가 노출됨
- HMAC timestamp/replay 검증 설정 오류

#### 사용자 영향
- forged event, replay attack, 내부 운영 정보 노출 위험이 생긴다.
- 실제 금융 데이터 원문이 유출되었는지 별도 보안 검토가 필요하다.

#### 탐지 방법
- Secret scan 결과, security log check, GitHub Actions secret scan
- [27-threat-model.md](27-threat-model.md), [28-secret-management-policy.md](28-secret-management-policy.md), [32-security-checklist.md](32-security-checklist.md)
- Nginx access control evidence와 masked log sample
- Manual check: report/blog/screenshot에 secret, token, account_no 원문이 없는지 확인

#### 대응 방법
- 1단계: 노출된 값의 종류와 범위를 분류한다.
- 2단계: 관련 secret을 rotate하고 이전 값을 폐기한다.
- 3단계: public/internal endpoint exposure를 점검한다.
- 4단계: 로그, report, screenshot에서 원문을 제거하거나 교체한다.
- 5단계: security checklist와 threat model에 재발 방지 항목을 추가한다.

#### 복구 검증
- secret scan과 security log check가 PASS다.
- 새 secret으로 smoke request가 정상 동작한다.
- 기존 secret은 더 이상 인증에 사용되지 않는다.
- README/blog/report에는 원문 secret, token, account_no, raw 거래 row data가 없다.

#### 재발 방지
- masking helper와 log policy를 강화한다.
- screenshot review checklist를 PR template 또는 runbook에 추가한다.
- HMAC secret rotation 주기와 owner를 문서화한다.

#### README/블로그 기록 문장
- 보안 사고 Runbook은 Threat Model, Secret Management, Security Checklist를 연결해 secret 노출 탐지, rotation, evidence sanitization 절차를 고정했다.

## 공통 템플릿

각 runbook은 아래 구조를 따른다.

1. 장애 상황
2. 예상 원인
3. 사용자 영향
4. 탐지 방법
5. 대응 방법
6. 복구 검증
7. 재발 방지
8. README/블로그 기록 문장
9. 사후 기록 템플릿

## Alert Rule 연결

각 Alert Rule에는 반드시 runbook 링크를 추가한다.

```yaml
annotations:
  runbook: "docs/runbooks/redis-down.md"
```

## Severity Level

| Severity | 기준 | 예시 |
|---|---|---|
| SEV1 | 금융 정합성 위반 또는 핵심 거래 처리 불가 | ledger 중복 반영, PostgreSQL down, secret leak |
| SEV2 | degraded mode 지속 또는 사용자 요청 실패 증가 | Redis down, Nginx 5xx spike, p99 급증 |
| SEV3 | 예방 대응 가능한 운영 위험 | disk 85%, backup 지연, dashboard 일부 누락 |
| SEV4 | 비긴급 개선 항목 | 문서 보완, alert threshold 조정 |

정합성 위반은 성능 저하와 다르게 error budget을 두지 않는다.
1건 발생 시 SEV1 incident로 분류한다.

## Incident Lifecycle

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
