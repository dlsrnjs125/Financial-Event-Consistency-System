# Incident Diagnosis Automation Design

> 자동화는 탐지, 분류, 차단, 증거 수집, 보고서 초안 생성까지 담당한다.
> 금전 상태 변경, write resume 승인, 고객 영향 판단, 외부 공지, 보안 예외 승인은 사람이 한다.

## 1. Incident Analyzer가 필요한 이유

기존 Runbook은 운영자가 장애 신호를 확인하는 순서를 제공한다.
Production Hardening에서는 Prometheus metric, structured log, k6 summary, consistency SQL 결과를 rule 기반으로 묶어 장애 유형과 심각도를 자동 분류하는 Incident Analyzer를 설계한다.

이 설계는 AI 자동 복구가 아니다.
우선순위는 deterministic rule 기반 판단이며, AI는 sanitized report를 요약하거나 Runbook 초안을 작성하는 보조 역할로만 둔다.
PH2에서는 full Incident Analyzer를 구현하지 않고, 후속 analyzer가 사용할 out-of-band artifact bundle과 sanitized report skeleton만 먼저 구현했다.
구현 세부사항은 [44-ph2-incident-artifact-sanitized-report.md](44-ph2-incident-artifact-sanitized-report.md)를 기준으로 한다.

## 2. 입력 데이터

| 입력 | 용도 | 민감정보 기준 |
| --- | --- | --- |
| Prometheus metric snapshot | latency, 5xx, dependency, Redis fallback, DB pressure 판단 | label에 raw account/key 금지 |
| k6 summary JSON | drill 결과와 성능 기준 비교 | synthetic event만 사용 |
| structured app logs | error_code, trace_id, event_id, dependency 확인 | raw body, signature, full key 금지 |
| Nginx access/error logs | 5xx, upstream, rate limit 확인 | client 식별자는 최소화 |
| PostgreSQL error logs | connection refused, deadlock, lock wait, disk/WAL 문제 확인 | query parameter 노출 주의 |
| Docker Compose service status | local drill에서 dependency 상태 확인 | 운영 secret 없음 |
| consistency SQL 결과 | duplicate, mismatch, orphan count 확인 | count-only 기본 |
| deployment status | active color, commit SHA, rollback 여부 확인 | public 가능 |

## 3. Signal Availability Matrix

현재 프로젝트는 FastAPI application metric 중심으로 관측성이 구현되어 있다.
PostgreSQL exporter, Redis exporter, Nginx log parser, HA replication metric은 후속 보완 후보이므로, Incident Analyzer는 현재 가능한 신호와 후속 구현 신호를 분리해서 사용한다.

| Signal | 현재 사용 가능 여부 | 현재 source | 후속 보완 |
| --- | --- | --- | --- |
| API 5xx rate | 가능 | FastAPI Prometheus metric | 유지 |
| `/ready` postgres fail | 가능 | readiness endpoint | 유지 |
| Redis fallback count | 가능 | app metric | 유지 |
| invalid state transition count | 가능 | app metric/log | 유지 |
| consistency SQL count | 가능 | 수동 SQL 또는 기존 verify command | analyzer query 자동화 |
| DB active connection usage | 제한적 | app log 또는 SQL 수동 조회 | PostgreSQL exporter 필요 |
| lock wait/deadlock count | 제한적 | SQL 수동 조회 | PostgreSQL exporter 또는 analyzer query 필요 |
| WAL/disk usage | 제한적 | Docker/host check | node/postgres exporter 필요 |
| Nginx upstream 5xx | 제한적 | Nginx log | log parser 필요 |
| metrics target down | 제한적 | Prometheus target page | alert/report 자동화 필요 |
| replication lag | 현재 불가 | HA 미구현 | HA 도입 시 가능 |
| Nginx request/upstream time | 제한적 | Nginx access log | log format/parser 보강 필요 |
| app phase duration | 후속 보완 | middleware/internal timer | phase timer 구현 필요 |
| outbound external HTTP duration | 후속 보완 | HTTP client wrapper | client instrumentation 필요 |
| external dependency probe | 후속 보완 | blackbox exporter 후보 | 핵심 endpoint probe 필요 |

Rule Matrix의 자동 판단은 현재 사용 가능한 신호만으로도 동작해야 한다.
후속 exporter가 필요한 신호는 confidence를 높이거나 세부 원인을 분류하는 보조 증거로 다룬다.

## 4. 자동 분류 가능한 장애 유형

- PostgreSQL down
- DB connection pool exhausted
- DB lock contention
- Redis down/degraded
- Nginx 5xx spike
- consistency violation
- invalid state transition
- metrics unavailable
- secret leak suspicion
- latency attribution

## 5. Severity 판단 기준

| Severity | 기준 | 예시 |
| --- | --- | --- |
| SEV1 | 금융 정합성 위반 또는 핵심 거래 처리 불가 | PostgreSQL down, duplicate ledger, secret leak |
| SEV2 | degraded mode 지속 또는 사용자 요청 실패 증가 | Redis down, Nginx 5xx spike, DB lock contention |
| SEV3 | 예방 대응 가능한 운영 위험 | metrics unavailable, disk warning |
| SEV4 | 비긴급 개선 항목 | threshold 조정, 문서 보완 |

정합성 위반은 error budget을 두지 않는다.
1건이라도 발생하면 SEV1로 분류한다.

## 6. Confidence score 기준

| Confidence | 의미 | 예시 |
| --- | --- | --- |
| 0.90 이상 | 여러 독립 신호가 같은 원인을 가리킴 | `/ready` postgres fail + connection refused + 5xx 증가 |
| 0.70~0.89 | 핵심 신호는 있으나 일부 evidence 부족 | Redis metric down + fallback 증가 |
| 0.50~0.69 | 가능성은 있으나 추가 확인 필요 | p99 증가 + lock wait 일부 증가 |
| 0.50 미만 | 자동 분류 보류 | metric target down으로 원인 불명 |

confidence는 운영자 판단을 대체하지 않는다.
보고서에는 primary signal과 missing evidence를 함께 기록한다.

## 7. 자동 판단 Rule Matrix

| 관측 결과 | 자동 판단 | Severity | 자동 조치 | 사람 판단 |
| --- | --- | --- | --- | --- |
| `/ready` postgres fail + connection refused | PostgreSQL down | SEV1 | write suspend, Retry-After, incident report 생성 | DB 복구 또는 failover 승인 |
| active connection 90% 이상 + pool timeout | DB pool exhausted | SEV1/SEV2 | rate limit 후보, batch 중지 후보, pool report 생성 | pool size/쿼리 개선 |
| lock wait 증가 + p99 증가 | DB lock contention | SEV2 | slow query/lock report, affected event 격리 후보 | transaction 수정 승인 |
| `redis_up=0` + fallback 증가 + 정합성 위반 0 | Redis degraded | SEV2 | degraded 유지, DB pressure 감시 | Redis 복구 |
| Nginx 5xx 증가 + app readiness 정상 | Gateway/upstream problem | SEV2 | upstream status 수집, rollback smoke 제안 | Nginx 설정 수정 |
| duplicate ledger count > 0 | Consistency violation | SEV1 | write suspend, affected account quarantine, recovery case 생성 | 보정 승인 |
| account balance mismatch > 0 | Consistency violation | SEV1 | recovery case 생성, affected account quarantine | 보정/보상 판단 |
| invalid state transition > 0 | Bad deployment or bypassed state machine | SEV1 | write suspend 또는 rollback 제안 | rollback 승인 |
| metrics target down + app 정상 | Observability incident | SEV3 | metrics incident 생성 | 모니터링 복구 |
| secret scan hit 또는 raw key log 의심 | Secret leak suspicion | SEV1 | affected context 격리, report 생성 | secret rotation, 외부 공지 판단 |

### Latency Attribution Rule Matrix

자세한 구간 분해와 metric/log 설계는 [41-latency-attribution-and-external-dependency-diagnosis.md](41-latency-attribution-and-external-dependency-diagnosis.md)를 기준으로 한다.
k6 기반 latency drill과 evidence 수집 계획은 [42-latency-drill-test-plan.md](42-latency-drill-test-plan.md)를 기준으로 한다.

| Rule | 조건 | 분류 | Severity | 자동 조치 | 수동 확인 |
| --- | --- | --- | --- | --- | --- |
| LAT-001 | app handler p95 정상 + partner reported latency 높음 | `external_or_network_suspected` | SEV3/SEV2 | partner evidence bundle 생성 | partner timestamp 대조 |
| LAT-002 | nginx request time 높음 + upstream response time 낮음 | `edge_or_client_network_latency` | SEV2 | Nginx log bundle 생성 | network 확인 |
| LAT-003 | app total high + DB phase high | `internal_postgres_latency` | SEV1/SEV2 | DB pressure analyzer 연결 | lock/query 분석 |
| LAT-004 | app total high + Redis phase high | `redis_degraded_latency` | SEV2 | Redis degraded mode 확인 | Redis 복구 |
| LAT-005 | app total high + outbound external HTTP high | `external_dependency_latency` | SEV2 | circuit breaker 후보 기록 | 외부사 장애 확인 |
| LAT-006 | all routes high | `internal_resource_saturation` | SEV1/SEV2 | global incident 생성 | CPU/DB/pool 확인 |
| LAT-007 | one client only high | `partner_specific_latency` | SEV3/SEV2 | client evidence 생성 | partner 계약 확인 |
| LAT-008 | blackbox probe high + app outbound high | `external_endpoint_slow` | SEV2 | external dependency incident 생성 | 외부사 확인 |
| LAT-009 | blackbox probe normal + app outbound high | `app_http_client_path_issue` | SEV2 | app client config 점검 | pool/DNS/TLS 확인 |

## 8. 자동 조치와 수동 조치의 경계

자동화해도 되는 조치:

- write suspend 활성화 후보 판단
- Retry-After 응답 정책 활성화 후보 생성
- Nginx rate limit 강화 후보 제안
- background job/reprocessor 일시 중지 후보 제안
- consistency SQL 실행
- recovery case 생성
- incident report 초안 생성
- sanitized AI context 생성
- latency evidence bundle 생성

사람이 해야 하는 조치:

- DB failover promote 승인
- backup restore 실행 승인
- 원장 보정 SQL 승인
- compensation ledger 생성 승인
- 고객/제휴사 영향도 확정
- 외부 공지 여부 결정
- secret rotation 최종 승인
- write resume 승인

## 9. AI 활용 가능 지점과 금지 지점

AI에게 맡길 수 있는 일:

- sanitized incident report 요약
- 로그 패턴 설명
- Runbook 초안 작성
- PromQL 후보 제안
- 테스트 케이스 초안 작성
- postmortem 초안 작성

AI에게 맡기면 안 되는 일:

- raw request body 분석
- 원문 계좌번호 또는 client secret 처리
- HMAC signature, Authorization header 수신
- 원장 보정 SQL 실행
- 고객 영향도 확정
- write resume 승인
- secret rotation 최종 승인

## 10. Incident report 자동 생성 형식

```json
{
  "incident_id": "inc-20260706-001",
  "scenario": "POSTGRES_DOWN",
  "severity": "SEV1",
  "confidence": 0.92,
  "primary_signals": [
    "readiness dependency postgres = 0",
    "5xx rate increased",
    "connection refused in app logs"
  ],
  "auto_actions": [
    "write_suspended",
    "retry_after_enabled",
    "consistency_check_scheduled",
    "incident_report_created"
  ],
  "manual_required": [
    "confirm DB recovery or failover",
    "approve write resume",
    "review recovery cases"
  ],
  "evidence_paths": [
    "reports/incidents/inc-20260706-001/metrics.json",
    "reports/incidents/inc-20260706-001/sanitized-logs.json"
  ]
}
```

## 11. 향후 Makefile target 후보

PH2에서는 artifact 생성과 검증 target만 구현했다.
full analyzer target은 후속 구현 후보로 관리한다.

PH2 구현 target:

```bash
make ph2-incident-artifact
make ph2-incident-artifact-validate
make ph2-db-down-incident-artifact
make ops10-incident-artifact
```

후속 analyzer 후보:

```bash
make incident-analyze
make incident-report
make recovery-cases
make ai-safe-incident-context
make latency-attribution-report
make latency-drill-report
```

성공 기준 후보:

- scenario, severity, confidence 산출
- 추천 runbook 링크 연결
- 자동 조치와 수동 조치 분리
- raw 계좌번호, raw idempotency key, signature 없는 sanitized report 생성
- internal/external latency responsibility 구간 후보 분류
- k6 latency drill result와 server metric/log 상관분석
