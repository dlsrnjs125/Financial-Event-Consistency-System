# 장애를 복구한 뒤 무엇을 남겨야 할까: Incident Timeline & Postmortem Drill

## 1. 왜 복구보다 기록이 중요한가

장애 대응에서 가장 위험한 문장은 "복구했습니다"일 수 있다.
언제 장애가 시작됐는지, 언제 탐지했는지, 어떤 영향이 있었는지, 어떤 검증으로 복구를
선언했는지 없으면 다음 장애 때 같은 질문을 다시 반복하게 된다.

Ops Phase 7에서는 복구 절차 자체보다 그 과정을 운영자가 읽을 수 있는 timeline과
postmortem evidence로 남기는 데 초점을 맞췄다.

## 2. Ops Phase 7의 목표

이번 Phase의 목표는 Redis degraded incident를 재현하고 다음 내용을 Markdown report로
남기는 것이다.

- incident started/detected/mitigated/recovered 시각
- detection latency와 recovery duration
- duplicate smoke 요청 결과
- duplicate ledger count 0
- idempotency violation count 0
- recovery verification PASS
- root cause와 follow-up action item

## 3. Redis degraded incident를 선택한 이유

Redis는 이 시스템에서 cache, lock, idempotency 보조 계층이다.
Redis가 내려가면 성능과 중복 요청 완화에는 영향이 있지만, PostgreSQL이 정상이라면
최종 정합성은 유지되어야 한다.

그래서 Redis degraded는 critical이 아니라 warning 성격의 incident로 본다.
다만 warning이라고 해서 기록하지 않아도 된다는 뜻은 아니다. fallback이 증가하고 DB에
중복 요청 압력이 전달될 수 있으므로 영향 확인과 사후 기록이 필요하다.

## 4. Incident Timeline을 어떻게 설계했나

Timeline은 STARTED, DETECTED, IMPACT_CHECK, MITIGATED, RECOVERED, VERIFIED로 나눴다.

STARTED는 controlled drill 시작 시각이다.
DETECTED는 `/ready`에서 Redis degraded를 확인한 시각이다.
IMPACT_CHECK에서는 Redis down 상태에서 duplicate smoke 요청을 두 번 보낸다.
MITIGATED는 Redis restart를 요청한 시점이고, RECOVERED는 readiness가 다시 PASS가 된
시점이다.
VERIFIED는 duplicate ledger count와 consistency check가 통과한 시점이다.

## 5. Impact Evidence는 무엇을 남겼나

Report에는 실제 거래 row data나 account_no 원문을 남기지 않는다.
대신 다음처럼 count-only evidence를 남긴다.

- first duplicate smoke status
- second duplicate smoke status
- event count for duplicate smoke
- ledger count for duplicate smoke
- idempotency record count for duplicate smoke
- duplicate ledger count
- idempotency violation count
- consistency check

이 방식은 운영자가 영향 범위를 판단할 수 있게 하면서도 민감 데이터가 report에 들어가는
것을 막는다.

## 6. Root Cause Analysis를 어떻게 정리했나

이번 drill의 immediate cause는 Redis container를 controlled drill로 stop한 것이다.
Root cause category는 Dependency degraded로 남긴다.

Source of Truth impact는 PostgreSQL consistency maintained로 기록한다.
User impact는 duplicate event request가 수락됐지만 duplicate ledger가 생기지 않은
상태로 정리한다.

## 7. Recovery Verification 기준

복구는 container start만으로 선언하지 않는다.

- Redis restarted
- health after recovery PASS
- ready after recovery PASS
- smoke after recovery PASS
- consistency after recovery PASS

이 기준을 모두 통과해야 postmortem report의 overall result를 PASS로 둔다.

## 8. 처음 기획과 달라진 점

처음에는 CI에서 전체 incident drill을 실행할 수도 있다고 생각했다.
하지만 Redis stop/start는 runner 상태, Docker timing, 이미지 준비 상태에 영향을 받기
쉽다. 그래서 CI에서는 script 문법과 curated report 형식을 검증하고, 실제 incident
drill evidence는 로컬 `make ops7-demo`로 남기는 방식으로 분리했다.

또한 실제 Slack, PagerDuty, Jira ticket 생성은 제외했다.
이번 Phase의 목적은 외부 연동이 아니라 postmortem의 구조와 evidence 기준을 고정하는
것이다.

## 9. Troubleshooting

현재 repo에는 `infra/loki`, `infra/promtail` 구성이 없다.
따라서 trace_id, request_id, event_id를 기반으로 한 완전한 log query evidence는 아직
제공하지 않는다. 이번 Phase에서는 Markdown postmortem과 count-only SQL evidence로
제한하고, 후속 Phase에서 OpenTelemetry 또는 Loki query evidence를 연결할 수 있다.

Drill 실패 시 script의 cleanup trap이 Redis를 다시 start한다.
그래도 readiness가 회복되지 않으면 `make ops7-up`과 `make ops7-check`로 스택 상태를
먼저 복구한다.

## 10. 이번 Phase에서 얻은 교훈

장애 대응은 복구 명령보다 기록 구조가 더 오래 남는다.
Timeline, impact evidence, root cause, recovery verification, action item이 같은
형식으로 남아야 다음 incident에서 더 빨리 판단할 수 있다.

Redis degraded는 전체 장애가 아니지만, 금융 이벤트 시스템에서는 중복 요청 압력이
PostgreSQL까지 도달할 수 있다. 그래서 warning incident라도 duplicate ledger 0건과
idempotency violation 0건을 반드시 evidence로 확인해야 한다.
