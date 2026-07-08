# PH11 Latency Drill Evidence Runner

## 1. Goal

PH11 adds a safe latency drill evidence runner for LAT-001~LAT-006.

The goal is to turn latency drill plans into reproducible, sanitized evidence that can be passed to the PH10 latency attribution analyzer. PH11 does not make p95/p99 a root-cause proof. It connects latency symptoms, server evidence, PH10 expected/actual classification, and consistency counters in one report.

## 2. Why PH11 Exists After PH10

PH10 implemented the deterministic analyzer that classifies sanitized latency evidence.

PH11 creates the evidence structure that feeds that analyzer. It records which latency drills are safe demo flows, which ones require manual opt-in, and whether PH10 returns the expected candidate classification.

## 3. Scope and Non-Scope

PH11 includes:

- LAT-001~LAT-006 deterministic drill catalog
- safe sample evidence generation
- PH10 input evidence generation
- PH10 analyzer integration
- expected vs actual PH10 classification validation
- JSON and Markdown drill reports
- Makefile targets for demo, validation, list, PH10 input generation, and PH11 safety check

PH11 does not include:

- production fault injection
- default DB lock holder execution
- default DB pool pressure mutation
- default Redis down or Redis delay execution
- default Nginx/network delay execution
- default mock partner slow endpoint execution
- Toxiproxy or netem implementation
- OpenTelemetry full tracing
- AI root-cause confirmation or automatic recovery

## 4. Drill Catalog

PH11 covers these drill entries:

| Drill | Goal | Expected PH10 Classification |
| --- | --- | --- |
| LAT-001 | baseline latency evidence | `baseline_normal_latency` |
| LAT-002 | PostgreSQL pool pressure evidence | `internal_postgres_pool_pressure` |
| LAT-003 | PostgreSQL lock contention evidence | `internal_postgres_lock_contention` |
| LAT-004 | Redis delay/down evidence | `redis_degraded_latency` |
| LAT-005 | external dependency slow response evidence | `external_endpoint_slow` |
| LAT-006 | Nginx edge/client latency evidence | `edge_or_client_network_latency` |

LAT-004 also supports a separate generated PH10 input scenario for `redis_unavailable`, which should classify as `redis_unavailable_fallback`.
LAT-005 also supports `app_http_client_path_issue` as a separate generated PH10 input scenario.

## 5. Safe Demo vs Manual Drill Boundary

The default PH11 demo only generates synthetic sanitized evidence and validates reports.

Manual or opt-in candidates:

- DB pool pressure with altered pool size
- controlled DB lock holder
- Redis down or Redis delay with network tooling
- mock partner slow endpoint
- Nginx edge/client network latency profile

These are not executed by `make ph11-latency-drill-demo`.

## 6. PH10 Analyzer Integration

PH11 imports `scripts/ph10_latency_attribution.py` and uses the PH10 analyzer as the only source of latency classification.

Each drill records:

- `expected_ph10_classification`
- `actual_ph10_classification`
- `ph10_input_scenario`

Validation fails if expected and actual classifications differ.

## 7. Evidence Structure

PH11 sample output lives under:

```text
reports/latency/ph11-drill-evidence/
```

Generated files:

- `sample-latency-drill-plan.json`
- `sample-latency-drill-plan.md`
- `sample-ph10-input-evidence.json`
- `sample-ph10-attribution-report.json`
- `sample-ph10-attribution-report.md`

## 8. Consistency Check Boundary

Latency drill evidence must include consistency counters:

- duplicate ledger count
- duplicate external event count
- reconciliation failure count
- invalid state transition count

If any counter is non-zero, the result is a consistency incident candidate before it is a latency issue. PH11 validation rejects reports that hide consistency violations as clean latency warnings.

## 9. Metric Label and Sensitive Data Policy

Allowed metric labels:

- `route_group`
- `endpoint_group`
- `partner_alias`
- `method`
- `status_code_family`
- `result`
- `phase`
- `operation`

Forbidden metric labels:

- `account_id`
- `event_id`
- `idempotency_key`
- `trace_id`
- `request_id`
- raw URL
- account/customer identifiers

PH11 reports must not include plain financial identifiers, plain retry identifiers, request payload contents, auth material, signing material, endpoint values, or database connection strings.

## 10. CLI and Makefile

CLI:

```bash
python3 scripts/ph11_latency_drill_runner.py demo
python3 scripts/ph11_latency_drill_runner.py validate --input reports/latency/ph11-drill-evidence/sample-latency-drill-plan.json
python3 scripts/ph11_latency_drill_runner.py list
python3 scripts/ph11_latency_drill_runner.py generate-ph10-input --scenario db_lock_contention --output reports/latency/ph11-drill-evidence/sample-ph10-input-evidence.json
```

Makefile:

```bash
make ph11-latency-drill-demo
make ph11-latency-drill-validate
make ph11-latency-drill-list
make ph11-latency-drill-generate-ph10-input
make ph11-latency-check
```

## 11. Validation Rules

The PH11 validator checks:

- required top-level fields
- required LAT-001~LAT-006 drill coverage
- default command target existence
- destructive/manual commands excluded from default commands
- manual drill boundary documentation
- expected PH10 classification enum validity
- expected vs actual PH10 classification match
- consistency violation priority
- k6-only root-cause claim rejection
- sensitive data pattern rejection
- forbidden metric label rejection
- AI root-cause or automatic recovery claim rejection

## 12. Relationship with Future Fault Injection

PH11 deliberately leaves Toxiproxy, netem, mock partner service, DB lock holder, and Redis delay profiles as manual or follow-up candidates.

This keeps the default demo reproducible and safe while preserving a clear path for future fault injection work.

## 13. Troubleshooting Notes

### k6 p95/p99 Becomes Root Cause Proof

- 문제: k6 latency spike만으로 DB, Redis, Nginx, external dependency 원인을 확정하려고 한다.
- 원인: k6는 client-visible symptom을 보여주지만 server phase timing을 직접 설명하지 못한다.
- 해결: PH11은 PH10 input evidence를 만들고 PH10 analyzer의 expected/actual classification을 비교한다.
- 검증: `test_k6_only_root_cause_claim_fails_validation`이 k6 단독 원인 확정 문구를 실패 처리한다.
- README에 넣지 않은 이유: README에는 PH11 역할만 요약하고 root-cause 해석 규칙은 이 문서에 둔다.

### Destructive Drill Runs In Default Demo

- 문제: DB lock holder, Redis down, network delay가 default demo에서 실행되면 로컬 개발 환경을 깨뜨릴 수 있다.
- 원인: latency drill과 evidence generation의 경계를 섞으면 안전한 샘플 실행이 어려워진다.
- 해결: PH11 default demo는 synthetic evidence만 생성하고 위험 동작은 manual/candidate command로 분리한다.
- 검증: `test_safe_auto_run_cannot_include_destructive_command`가 destructive default command를 실패 처리한다.
- README에 넣지 않은 이유: manual boundary 상세는 문서와 report validator가 관리한다.

### Missing Makefile Target Looks Executable

- 문제: 아직 없는 target을 default `commands`에 넣으면 report만 보고 실행 가능하다고 오해할 수 있다.
- 원인: drill catalog가 candidate와 executable command를 구분하지 않으면 운영자가 잘못 실행할 수 있다.
- 해결: default `commands`는 실제 Makefile target만 허용하고 후보는 `candidate_commands`나 `manual_commands`로 분리한다.
- 검증: `test_default_command_must_exist_in_makefile`이 없는 target을 실패 처리한다.
- README에 넣지 않은 이유: README에는 대표 PH11 명령만 둔다.

### PH10 Expected And Actual Classification Mismatch

- 문제: drill이 기대한 classification과 PH10 analyzer 결과가 달라도 report가 통과할 수 있다.
- 원인: PH11이 자체 root cause 판단을 만들면 PH10 analyzer와 기준이 어긋날 수 있다.
- 해결: report에 expected/actual PH10 classification을 모두 기록하고 mismatch를 validation error로 처리한다.
- 검증: `test_expected_actual_classification_mismatch_fails_validation`이 mismatch를 실패 처리한다.
- README에 넣지 않은 이유: expected/actual 비교는 PH11 내부 계약이다.

### Consistency Violation Hidden By Latency

- 문제: duplicate ledger나 reconciliation failure가 p99 latency issue에 묻힐 수 있다.
- 원인: retry storm 상황에서는 performance symptom과 consistency signal이 동시에 나타날 수 있다.
- 해결: PH11 consistency policy는 non-zero counter를 latency보다 우선하는 incident candidate로 둔다.
- 검증: `test_consistency_violation_cannot_be_reported_as_clean_latency`가 clean latency 표현을 실패 처리한다.
- README에 넣지 않은 이유: consistency escalation은 SLO/runbook 문서와 PH11 문서가 관리한다.

### High-Cardinality Metric Label Leaks Into Report

- 문제: `trace_id`, `request_id`, `event_id`, retry key 같은 값을 metric label 후보로 넣을 수 있다.
- 원인: 단일 요청 디버깅 편의와 Prometheus cardinality/security policy가 충돌한다.
- 해결: PH11 validator는 forbidden metric label을 탐지하고 bounded labels만 허용한다.
- 검증: `test_forbidden_metric_label_fails_validation`이 forbidden label을 실패 처리한다.
- README에 넣지 않은 이유: label allowlist는 상세 운영 정책이다.

### Mock Partner Overstates External Dependency Proof

- 문제: mock partner evidence를 실제 외부사 장애의 완전한 대체재로 오해할 수 있다.
- 원인: 반복 가능한 mock은 재현성은 좋지만 실제 provider network와 SLA를 그대로 대표하지 않는다.
- 해결: PH11 report는 mock partner를 manual/follow-up candidate로 두고, 완전 검증이라고 표현하지 않는다.
- 검증: `test_markdown_report_contains_contract_boundaries`가 manual boundary와 sensitive policy를 확인한다.
- README에 넣지 않은 이유: mock partner 한계는 PH11 상세 문서와 blog에서 설명한다.

### README Becomes A Drill Catalog

- 문제: LAT-001~LAT-006 상세를 README에 모두 넣으면 프로젝트 요약성이 떨어진다.
- 원인: PH11은 drill catalog가 핵심 산출물이지만 README는 포트폴리오 index 역할이다.
- 해결: README에는 PH11 한 문장, 문서 링크, 대표 명령만 추가한다.
- 검증: PH11 상세 catalog는 `sample-latency-drill-plan.json`과 이 문서에서 확인한다.
- README에 넣지 않은 이유: README 자체를 장황하게 만들지 않는 것이 목적이다.

## 14. Limits and Next Steps

PH11 is a safe evidence runner, not a complete fault injection lab.

Next candidates:

- controlled DB lock holder with timeout cleanup
- Redis delay profile using Toxiproxy or netem
- mock partner compose profile
- Nginx timing parser
- OpenTelemetry trace expansion
- Grafana latency attribution dashboard
