# 장애를 찾았다고 바로 고치면 더 위험했다

장애 분석기가 "문제가 있어 보인다"고 말해도, 금융 이벤트 시스템에서 바로 복구를 실행하면 더 큰 사고가 될 수 있다.

이 글은 장애 artifact를 분석하고, 복구 후보를 격리하고, 오래 남은 `PROCESSING` 상태를 자동 수정하지 않도록 분리한 운영 판단 흐름을 정리한다.

## 운영 판단 흐름

복구 흐름은 자동 실행이 아니라 후보 생성과 수동 승인으로 나눴다.

```text
Sanitized Artifact
  -> Analyzer Classification
  -> Recovery Case Candidate
  -> Quarantine
  -> Manual Approval
  -> Recovery Execution
  -> Verification
```

Analyzer는 장애 후보를 분류할 뿐이다. Recovery case는 "고쳤다"가 아니라 "운영자가 판단할 후보를 안전하게 격리했다"는 의미다.

## Analyzer는 AI 판단기가 아니라 deterministic classifier다

Analyzer는 ML 모델이나 AI 판단기가 아니다. 정해진 artifact와 count-only evidence를 보고 deterministic rule로 분류한다.

이 제한을 둔 이유는 복구 판단이 설명 가능해야 하고, 같은 입력에 대해 같은 결과가 나와야 하기 때문이다. 운영자가 검토할 수 없는 추론 결과가 원장 보정이나 상태 변경으로 이어지면 안 된다.

## 왜 자동 복구하지 않았나

금융 이벤트 시스템에서 잘못된 자동 복구는 누락보다 더 위험할 수 있다. 이미 원장이 반영된 이벤트를 다시 보정하거나, 처리 중인 이벤트를 실패로 확정하면 새로운 정합성 사고가 된다.

그래서 analyzer output은 recovery execution으로 바로 이어지지 않는다. quarantine과 manual approval boundary를 둔다.

## 트러블슈팅 1: manifest 누락은 민감정보 유출이 아니다

`manifest.json`이 없으면 artifact 구성을 알 수 없다. 하지만 그것만으로 raw account number나 signature가 포함됐다고 단정할 수는 없다.

처음에는 manifest가 없으면 sanitization risk로 볼 수 있다고 생각했다. 하지만 이 분류는 너무 강하다.

그래서 다음처럼 나눴다.

- `INSUFFICIENT_EVIDENCE`: artifact 구조를 판단할 근거가 부족함
- `ARTIFACT_SANITIZATION_RISK`: 민감정보 포함 가능성이 실제로 감지됨

manifest 누락은 `INSUFFICIENT_EVIDENCE`다. evidence가 부족하다는 것과 민감정보가 유출됐다는 것은 다르다.

## 트러블슈팅 2: stale PROCESSING을 자동 완료하지 않았다

오래 남은 `PROCESSING`은 여러 의미를 가질 수 있다.

- 실제로 처리 중이다.
- ledger는 생성됐지만 상태 업데이트가 누락됐다.
- 외부 dependency 응답 대기 중이다.
- 장애로 멈췄다.

막 생성된 `PROCESSING`을 바로 mismatch로 잡으면 오탐이 된다. 그래서 stale threshold를 두고 count-only evidence를 만든 뒤 recovery case 후보로 넘긴다.

자동 완료나 자동 실패 처리는 하지 않는다.

## 트러블슈팅 3: recovery case 자체가 유출 경로가 될 수 있다

Analyzer result가 안전하지 않은데 recovery case로 저장하면, 복구 시스템 자체가 민감정보 저장소가 될 수 있다.

그래서 `sensitive_data_included=false`가 아니면 case 생성을 거부한다.

```text
unsafe analyzer result
-> recovery case creation refused
-> operator must inspect sanitized artifact path
```

recovery system은 장애를 고치는 도구이기 전에, 민감정보를 오래 보관하지 않아야 하는 저장 경계다.

## evidence는 실행 권한이 아니다

Recovery case에는 classification, severity, candidate action, sanitized evidence path를 남긴다. 하지만 이것은 실행 승인과 다르다.

```text
case created
-> operator review required
-> approval recorded
-> execution command selected
-> post-check required
```

이 경계를 둔 이유는 analyzer가 틀릴 수 있기 때문이다. analyzer가 원인을 좁히는 데 도움을 줄 수는 있지만, 원장 보정이나 상태 변경을 자동으로 결정하면 안 된다.

## 복구 후보도 idempotent해야 한다

장애 분석 결과는 사람이 여러 번 실행할 수 있다. 같은 incident artifact를 여러 번 ingest하면 같은 복구 후보가 중복 생성될 수 있다.

그래서 `source_key`를 유일하게 만들고, repeated create-from-analysis는 기존 case를 반환하도록 했다.

복구 후보도 idempotent하지 않으면 운영자가 같은 사고를 두 번 처리할 수 있다.

## active quarantine은 target별로 하나만 존재해야 한다

동시에 두 운영자가 같은 account나 event를 quarantine하면 active record가 두 개 생길 수 있다.

그래서 service-level lookup과 PostgreSQL partial unique index로 중복 active quarantine을 막았다.

운영 도구에도 동시성 방어가 필요했다.

## quarantine은 사용자 데이터를 바로 바꾸는 기능이 아니다

이 글에서 말하는 quarantine은 운영 판단을 위한 격리 기록이다. 즉, 특정 account나 event가 위험 후보라는 사실을 남기고, recovery case와 연결해 운영자가 검토할 수 있게 만드는 장치다.

이번 프로젝트의 quarantine은 실제 계좌를 동결하거나, 고객 거래를 차단하거나, ledger를 자동 수정하지 않는다. 그런 기능은 훨씬 강한 권한 모델과 승인 절차가 필요하다.

실제 운영에서 quarantine이 user-facing action이 되려면 다음이 추가되어야 한다.

- 어떤 대상이 격리되는지에 대한 명확한 정책
- 운영자 권한과 승인 단계
- 고객 영향 범위 계산
- release 조건
- 감사 로그
- compensation 또는 correction ledger 정책
- 잘못 격리했을 때의 복구 절차

따라서 이번 글의 quarantine은 자동 보정이 아니라, 복구 후보를 중복 없이 안전하게 묶어두는 운영 evidence layer에 가깝다.

## stale reconciliation의 역할

stale reconciliation은 "오래된 PROCESSING을 찾아 자동으로 고친다"가 아니라, count-only evidence를 만들어 recovery 판단으로 넘기는 역할이다.

fresh event를 오탐하지 않기 위해 threshold를 두고, 실제 row 원문 대신 집계와 tokenized identifier 중심으로 report를 만든다.

모든 event without ledger를 같은 mismatch로 세지 않았다.

| 상태 | ledger 없음 판단 |
| --- | --- |
| `COMPLETED`, `CANCELLED`, `SETTLED` | 즉시 정합성 후보 |
| `RECEIVED`, `VALIDATED`, `PROCESSING` | stale threshold 이후 후보 |
| `FAILED` | 정상 실패일 수 있어 제외 |

## 남은 한계

이 흐름은 실제 원장 보정 자동화를 제공하지 않는다. 보정 실행은 별도 승인, audit trail, compensation ledger 정책이 필요하다.

현재 단계의 목적은 장애 후보를 분류하고, 복구 판단에 필요한 evidence를 안전한 형태로 격리하는 것이다.
