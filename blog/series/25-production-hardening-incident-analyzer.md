# 장애 증거를 모은 뒤, 자동 판단은 어디까지 가능할까

PH2에서 PostgreSQL 장애 중에도 out-of-band artifact를 남겼다. 하지만 evidence bundle은 판단이 아니다. 운영자는 여전히 이 장애가 PostgreSQL down인지, 정합성 위험인지, 민감정보 위험인지 직접 읽어야 했다.

PH3의 질문은 이것이었다.

```text
장애 증거를 모은 뒤, 어디까지 자동으로 판단해도 되는가?
```

## 수동 로그 확인만으로는 느리다

장애 상황에서 운영자가 `manifest.json`, write suspend state, readiness summary, consistency summary를 모두 읽고 판단하면 느리다. 반복되는 판단은 rule로 고정할 수 있다.

다만 자동 판단이 곧 자동 복구가 되면 위험하다. 특히 금융 이벤트 시스템에서는 classification과 recovery execution 사이에 승인 경계가 있어야 한다.

## Analyzer를 복구 실행자가 아니라 분류기로 제한한 이유

PH3의 analyzer는 deterministic rule 기반이다. AI API를 호출하지 않고, DB를 고치지도 않고, recovery case를 실행하지도 않는다.

역할은 다음으로 제한했다.

- incident classification 후보 생성
- severity/confidence 후보 생성
- primary signal 정리
- manual action 후보 제안
- runbook link 제안
- `manual_review_required=true` 유지

이 제한 덕분에 analyzer output은 운영자 판단을 돕는 초안이지, 복구 승인 기록이 아니다.

## Rule priority를 먼저 고정했다

PH3 MVP rule priority는 다음 순서다.

```text
1. ARTIFACT_SANITIZATION_RISK
2. CONSISTENCY_ISSUE_CANDIDATE
3. POSTGRES_DOWN_WRITE_SUSPENDED
4. WRITE_SUSPENDED_UNKNOWN_DEPENDENCY
5. INSUFFICIENT_EVIDENCE
6. UNKNOWN_INCIDENT
```

민감정보 위험을 가장 앞에 둔 이유는 단순하다. artifact가 안전하지 않으면 그 뒤의 분석 결과를 공유하거나 AI-safe context로 넘기면 안 된다.

정합성 후보도 dependency 장애보다 먼저 본다. duplicate ledger 같은 count가 0보다 크면 금전 영향 가능성이 있으므로, PostgreSQL down 여부보다 먼저 incident 후보로 올린다.

## Count-only summary를 사용한 이유

Analyzer가 raw ledger row나 raw request를 읽지 않게 했다. 대신 PH2/PH5에서 만든 count-only consistency summary를 읽는다.

이 선택은 설명력과 안전성의 절충이다. 구체 row를 보지 않으므로 자동 복구 판단은 할 수 없지만, 정합성 위험 후보를 빠르게 분류하고 수동 확인으로 넘길 수 있다.

## 실제로 보강한 트러블슈팅

처음에는 `manifest.json`이 없는 artifact를 sanitization risk처럼 처리할 위험이 있었다. 하지만 manifest 누락은 민감정보 유출이 아니라 evidence 부족이다. 그래서 `INSUFFICIENT_EVIDENCE`로 분리했다.

또 write suspend가 active인 경우에도 scenario가 PostgreSQL down인지 모르면 `POSTGRES_DOWN_WRITE_SUSPENDED`로 단정하지 않고 `WRITE_SUSPENDED_UNKNOWN_DEPENDENCY`로 낮췄다. 이 차이는 자동 분석이 과장되지 않게 만드는 작은 경계다.

## 검증한 것

테스트는 PostgreSQL down + write suspend, unknown dependency, sanitization risk priority, consistency issue priority, missing manifest, analyzer output validation을 확인한다.

특히 analyzer output 자체도 `sensitive_data_included=false`여야 한다. 분석 결과가 다시 유출 경로가 되면 PH3의 의미가 사라진다.

## 이 글에서 말할 수 있는 것과 말하면 안 되는 것

말할 수 있는 것은 PH3가 sanitized evidence를 기반으로 incident classification 후보를 deterministic하게 만든다는 점이다.

말하면 안 되는 것은 PH3가 자동 복구를 실행하거나, AI가 장애 원인을 확정하거나, write resume을 승인한다는 주장이다. PH3는 복구 실행자가 아니라 분류기다.
