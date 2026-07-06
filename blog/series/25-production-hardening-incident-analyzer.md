# 장애 로그를 모았으면, 그다음에는 무엇을 자동화해야 할까

## 1. 문제 상황

PH2에서는 PostgreSQL 장애 중에도 DB에 의존하지 않는 out-of-band incident artifact를 남겼다.
하지만 artifact를 남기는 것만으로 운영 판단이 빨라지는 것은 아니다.

운영자는 여전히 다음 질문에 답해야 한다.

```text
이 장애는 어떤 유형인가?
severity 후보는 무엇인가?
confidence는 어느 정도인가?
어떤 수동 조치가 필요한가?
어떤 runbook을 먼저 봐야 하는가?
```

PH3의 목표는 이 질문에 대한 1차 답변을 deterministic rule로 만드는 것이다.

## 2. PH2 artifact만으로는 부족했던 점

PH2 artifact는 증거 묶음이다.
`manifest.json`, `write-suspend-state.json`, `consistency-summary.json`, `sanitized-report.md`는 운영자가 볼 수 있는 재료를 제공한다.

하지만 raw evidence bundle은 판단 자체가 아니다.
PostgreSQL down인지, 정합성 위험 후보인지, 민감정보 위험 때문에 공유를 중단해야 하는지 같은 판단은 별도 rule이 필요하다.

## 3. 선택한 방식: Rule-based Incident Analyzer

PH3는 `scripts/ph3_incident_analyzer.py`를 추가했다.

명령은 단순하다.

```bash
python scripts/ph3_incident_analyzer.py analyze --latest
python scripts/ph3_incident_analyzer.py validate --latest
```

Makefile에서는 다음 target으로 실행한다.

```bash
make ph3-incident-analyze
make ph3-incident-analyze-validate
make ph3-db-down-incident-analysis
```

분석 결과는 incident artifact directory 안에 남긴다.

```text
analyzer-result.json
incident-analysis.md
```

## 4. AI가 아니라 deterministic rule부터 선택한 이유

장애 분석에 AI를 바로 붙일 수도 있다.
하지만 금융 이벤트 시스템에서는 민감정보와 금전 상태 변경 책임이 중요하다.

그래서 PH3에서는 AI API를 호출하지 않는다.
대신 다음 원칙을 둔다.

- 민감정보 위험은 가장 먼저 차단한다.
- 정합성 위반 후보는 PostgreSQL down보다 우선한다.
- write resume, DB failover, recovery case 생성은 사람이 판단한다.
- analyzer output은 운영자 검토용 초안이다.

## 5. Rule Priority

PH3 MVP rule priority는 다음 순서다.

```text
1. ARTIFACT_SANITIZATION_RISK
2. CONSISTENCY_ISSUE_CANDIDATE
3. POSTGRES_DOWN_WRITE_SUSPENDED
4. WRITE_SUSPENDED_UNKNOWN_DEPENDENCY
5. INSUFFICIENT_EVIDENCE
6. UNKNOWN_INCIDENT
```

민감정보 위험을 가장 먼저 둔 이유는 명확하다.
artifact가 안전하지 않으면 AI나 외부 문서에 공유하면 안 된다.

정합성 후보를 PostgreSQL down보다 앞에 둔 이유도 같다.
duplicate ledger 같은 count가 0보다 크면 금전 영향 가능성이 있으므로 dependency 장애보다 먼저 다뤄야 한다.

## 6. Analyzer Output

`analyzer-result.json`에는 다음 정보가 들어간다.

- incident id
- analyzer version
- classification
- severity candidate
- confidence candidate
- primary signals
- observed auto actions
- manual actions required
- recommended runbooks
- limits
- `manual_review_required=true`
- `sensitive_data_included=false`

`incident-analysis.md`는 운영자가 읽기 쉬운 Markdown 초안이다.

## 7. PH1/PH2 Drill과 연결

PH1은 PostgreSQL down 중 성공 응답을 막았다.
PH2는 그 상황의 sanitized artifact를 남겼다.
PH3는 그 artifact를 읽어서 classification 후보를 만든다.

Docker 기반 전체 흐름은 다음 target으로 연결했다.

```bash
make ph3-db-down-incident-analysis
```

이 target은 PH2 DB-down artifact flow를 실행한 뒤 최신 artifact를 analyze/validate한다.

## 8. 트러블슈팅

개발 중 확인한 주의사항:

- PH3는 `raw/` 디렉터리를 읽지 않는다.
- PH2 validation에서 민감정보 위험이 나오면 PH3는 `ARTIFACT_SANITIZATION_RISK`로 분류한다.
- `manifest.json`이 없으면 복구 판단을 추정하지 않고 `INSUFFICIENT_EVIDENCE`로 낮은 confidence를 둔다.
- analyzer output 자체도 `sensitive_data_included=false`여야 한다.

## 9. 검증 결과

추가한 테스트는 다음을 검증한다.

- PostgreSQL down + write suspend active는 `POSTGRES_DOWN_WRITE_SUSPENDED`
- scenario unknown + write suspend active는 `WRITE_SUSPENDED_UNKNOWN_DEPENDENCY`
- sanitization risk는 consistency issue보다 우선
- duplicate ledger count가 0보다 크면 `CONSISTENCY_ISSUE_CANDIDATE`
- manifest가 없으면 `INSUFFICIENT_EVIDENCE`
- analyze가 `analyzer-result.json`과 `incident-analysis.md`를 생성
- validate가 정상 analyzer output을 통과
- validate가 `sensitive_data_included=true` output을 실패 처리

로컬 Docker 기반 full drill은 환경에 따라 별도 실행이 필요하다.

## 10. 남은 한계

PH3는 아직 MVP다.

하지 않는 일:

- recovery case DB 모델 생성
- 자동 복구 실행
- write resume 자동 승인
- AI API 호출
- Slack/PagerDuty 전송
- live Prometheus query
- latency phase instrumentation

## 11. 다음 단계

다음 단계는 PH-Impl 4 Recovery Case / Quarantine / Manual Approval이다.
PH3가 만든 classification과 manual action 후보를 바탕으로, 실제 복구 후보를 DB-backed recovery case로 관리하는 흐름을 설계하고 구현하는 단계다.
